# check_ssl_labs.py

A Nagios / Icinga / Checkmk compatible plugin for monitoring HTTPS SSL/TLS configurations using the **Qualys SSL Labs API v4**.

It evaluates host configurations against SSL Labs letter grades (`A+` down to `F`), supports multi-endpoint hosts, returns performance data metrics, and respects SSL Labs rate limits by querying cached assessments first.

## Prerequisites

* Python 3.12 or higher (3.6 should work, but I haven't tested).
* Outbound network access to [https://api.ssllabs.com](https://api.ssllabs.com).
* An organizational email address for SSL Labs API v4 registration.

## Installation

1. Copy `check_ssl_labs.py` to your monitoring plugins directory (e.g., `/usr/lib/nagios/plugins/`).
2. Make the file executable:

```bash
chmod +x /usr/lib/nagios/plugins/check_ssl_labs.py

```

## Register Your Email with SSL Labs API v4

SSL Labs API v4 requires a registered email header with all API requests. You must run a one-time registration command before running checks:

```bash
/usr/lib/nagios/plugins/check_ssl_labs.py --register \
  -e "admin@yourdomain.com" \
  --first-name "Monika" \
  --last-name "Musterfrau" \
  --org "My Company"

```

## Command Line Usage

```text
usage: check_ssl_labs.py [-h] [--register] [--first-name FIRST_NAME]
                         [--last-name LAST_NAME] [--org ORG]
                         [-H HOSTNAME] -e EMAIL [-w WARNING] [-c CRITICAL]
                         [-m MAX_AGE]

Nagios/Icinga check for SSL certs via SSL Labs API v4

options:
  -h, --help            show this help message and exit
  -H HOSTNAME, --hostname HOSTNAME
                        Domain/Host to test (Required unless using --register)
  -e EMAIL, --email EMAIL
                        Registered SSL Labs v4 email address (Required)
  -w WARNING, --warning WARNING
                        Warning grade threshold (default: B). Triggers if grade is worse.
  -c CRITICAL, --critical CRITICAL
                        Critical grade threshold (default: C). Triggers if grade is worse.
  -m MAX_AGE, --max-age MAX_AGE
                        Maximum cache age in hours (default: 24)

Registration Options:
  --register            Register email address with SSL Labs API v4
  --first-name FIRST_NAME
                        First name for registration (default: Admin)
  --last-name LAST_NAME
                        Last name for registration (default: User)
  --org ORG             Organization name for registration (default: Ops Team)

```

### Examples

**Check a website using default thresholds (Warning if worse than `B`, Critical if worse than `C`):**

```bash
./check_ssl_labs.py -H www.example.com -e "admin@yourdomain.com"

```

**Strict check (Warning if below `A`, Critical if below `A-`):**

```bash
./check_ssl_labs.py -H www.example.com -e "admin@yourdomain.com" -w A -c A-

```

**Check with a custom cache age of 12 hours:**

To avoid hitting rate limits, this scripts uses cached results if available. Max cache age can be changed, but be careful.

```bash
./check_ssl_labs.py -H www.example.com -e "admin@yourdomain.com" -m 12

```

## Monitoring System Integration

### Nagios / Icinga 1.x

#### `commands.cfg`

```nagios
define command {
    command_name    check_ssllabs
    command_line    /usr/lib/nagios/plugins/check_ssl_labs.py -H $HOSTADDRESS$ -e "$ARG1$" -w $ARG2$ -c $ARG3$
}

```

#### `services.cfg`

Because uncached assessments can take several minutes, set a generous service check timeout and run checks once or twice a day:

```nagios
define service {
    use                     generic-service
    host_name               example.com
    service_description     SSL Labs Grade
    check_command           check_ssllabs!admin@yourdomain.com!B!C
    check_interval          1440        ; Check once per day (1440 minutes)
    retry_interval          360         ; Retry after 6 minutes for live scans
}

```

### Icinga 2

TODO. Please provide a pull request if you successully added this to Icinga 2.

### Checkmk

TODO. Please provide a pull request if you successfully added this to Checkmg.

## Exit Codes & Output Format

| Exit Code | Label | Trigger Condition |
| --- | --- | --- |
| 0 | OK | All endpoint grades meet or exceed warning/critical thresholds. |
| 1 | WARNING | One or more endpoint grades fall below the warning threshold (or API overloaded). |
| 2 | CRITICAL | One or more endpoint grades fall below the critical threshold (or API rate limit hit). |
| 3 | UNKNOWN | HTTP/Network error, invalid arguments, or missing registered email header. |

### Sample Output

```text
SSL LABS OK - Host www.example.com -> [93.184.216.34 Grade: A+] | '93.184.216.34_score'=100;;;0;100

```
