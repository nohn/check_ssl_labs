#!/usr/bin/env python3
"""
Nagios/Icinga/Checkmk Plugin for SSL Labs API v4
Includes self-registration support for API v4.
"""

import sys
import json
import time
import argparse
import urllib.request
import urllib.parse
import urllib.error

# Nagios Exit Codes
OK = 0
WARNING = 1
CRITICAL = 2
UNKNOWN = 3

GRADE_MAP = {
    "A+": 100, "A": 90, "A-": 85,
    "B": 75, "C": 65, "D": 50,
    "E": 35, "F": 20, "T": 0, "M": 0
}

def exit_with(status, message):
    labels = {OK: "OK", WARNING: "WARNING", CRITICAL: "CRITICAL", UNKNOWN: "UNKNOWN"}
    print(f"SSL LABS {labels.get(status, 'UNKNOWN')} - {message}")
    sys.exit(status)

def register_email(email, first_name, last_name, organization):
    """Registers an email address with SSL Labs API v4."""
    url = "https://api.ssllabs.com/api/v4/register"
    payload = {
        "firstName": first_name,
        "lastName": last_name,
        "email": email,
        "organization": organization
    }
    
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            print(f"Registration successful for {email}: {json.dumps(res_data, indent=2)}")
            sys.exit(OK)
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        exit_with(UNKNOWN, f"Registration failed (HTTP {e.code}): {error_body}")
    except Exception as e:
        exit_with(UNKNOWN, f"Network error during registration: {str(e)}")

def make_api_request(url, email):
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "Nagios-Check-SSLLabs/4.0")
    if email:
        req.add_header("email", email)

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 400:
            exit_with(UNKNOWN, "HTTP 400 Bad Request. Ensure you provided a registered email via -e / --email.")
        elif e.code == 429:
            exit_with(CRITICAL, "API rate limit reached (HTTP 429).")
        elif e.code == 529:
            exit_with(WARNING, "SSL Labs service is overloaded (HTTP 529).")
        else:
            exit_with(UNKNOWN, f"HTTP Error {e.code}: {e.reason}")
    except Exception as e:
        exit_with(UNKNOWN, f"Network error: {str(e)}")

def poll_ssllabs(hostname, max_age, email):
    base_url = "https://api.ssllabs.com/api/v4/analyze"
    
    cache_params = {
        "host": hostname,
        "fromCache": "on",
        "all": "done",
        "maxAge": str(max_age)
    }
    url = f"{base_url}?{urllib.parse.urlencode(cache_params)}"
    data = make_api_request(url, email)

    status = data.get("status")

    if status not in ["READY", "IN_PROGRESS", "DNS"]:
        start_params = {
            "host": hostname,
            "startNew": "on",
            "all": "done"
        }
        url = f"{base_url}?{urllib.parse.urlencode(start_params)}"
        data = make_api_request(url, email)
        status = data.get("status")

    max_retries = 30
    retries = 0
    while status in ["DNS", "IN_PROGRESS"] and retries < max_retries:
        time.sleep(10)
        poll_params = {"host": hostname, "all": "done"}
        url = f"{base_url}?{urllib.parse.urlencode(poll_params)}"
        data = make_api_request(url, email)
        status = data.get("status")
        retries += 1

    if status == "ERROR":
        status_msg = data.get("statusMessage", "Unknown error on SSL Labs side.")
        exit_with(CRITICAL, f"Scan failed for {hostname}: {status_msg}")

    if status != "READY":
        exit_with(UNKNOWN, f"Assessment timed out for {hostname}. Status: {status}")

    return data

def compare_grades(grade, threshold):
    val_grade = GRADE_MAP.get(grade.upper(), 0)
    val_thresh = GRADE_MAP.get(threshold.upper(), 0)
    return val_grade < val_thresh

def parse_args():
    parser = argparse.ArgumentParser(description="Nagios/Icinga check for SSL certs via SSL Labs API v4")
    
    # Registration sub-group
    reg_group = parser.add_argument_group("Registration Options")
    reg_group.add_argument("--register", action="store_true", help="Register email address with SSL Labs API v4")
    reg_group.add_argument("--first-name", default="Admin", help="First name for registration")
    reg_group.add_argument("--last-name", default="User", help="Last name for registration")
    reg_group.add_argument("--org", default="Ops Team", help="Organization name for registration")

    # Regular check arguments
    parser.add_argument("-H", "--hostname", help="Domain/Host to test (Required unless using --register)")
    parser.add_argument("-e", "--email", required=True, help="Registered SSL Labs v4 email address")
    parser.add_argument("-w", "--warning", default="B", help="Warning grade threshold (default: B)")
    parser.add_argument("-c", "--critical", default="C", help="Critical grade threshold (default: C)")
    parser.add_argument("-m", "--max-age", type=int, default=24, help="Maximum cache age in hours (default: 24)")

    args = parser.parse_args()

    # Enforce -H if not running registration mode
    if not args.register and not args.hostname:
        parser.error("-H/--hostname is required unless running in --register mode.")

    return args

def main():
    args = parse_args()

    # If --register flag is passed, perform registration and exit
    if args.register:
        register_email(
            email=args.email,
            first_name=args.first_name,
            last_name=args.last_name,
            organization=args.org
        )

    # Standard Nagios check mode
    max_age_seconds = args.max_age * 3600
    data = poll_ssllabs(args.hostname, max_age_seconds, args.email)

    endpoints = data.get("endpoints", [])
    if not endpoints:
        exit_with(CRITICAL, f"No reachable endpoints found for {args.hostname}")

    worst_status = OK
    summary_parts = []
    perf_data = []

    for ep in endpoints:
        ip = ep.get("ipAddress", "unknown")
        grade = ep.get("grade", "N/A")
        status_msg = ep.get("statusMessage", "")

        if grade == "N/A":
            summary_parts.append(f"[{ip}: {status_msg}]")
            worst_status = max(worst_status, CRITICAL)
            continue

        ep_status = OK
        if compare_grades(grade, args.critical):
            ep_status = CRITICAL
        elif compare_grades(grade, args.warning):
            ep_status = WARNING

        worst_status = max(worst_status, ep_status)
        summary_parts.append(f"[{ip} Grade: {grade}]")

        numeric_score = GRADE_MAP.get(grade, 0)
        perf_data.append(f"'{ip}_score'={numeric_score};;;0;100")

    message = f"Host {args.hostname} -> " + ", ".join(summary_parts)
    if perf_data:
        message += " | " + " ".join(perf_data)

    exit_with(worst_status, message)

if __name__ == "__main__":
    main()
