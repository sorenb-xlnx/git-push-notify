# Git push-notify

Git push helper for maintainers to notify stakeholders when patches have been
applied.

The script is based on GregKH's [maintainer
scripts](https://github.com/gregkh/gregkh-linux) and the tip-bot's emails.

## Configuration
The script requies user-specific configuratin options to be provided.
Options are read from a config file (~/.pushrc). A sample file is provided in
`pushrc.sample`.

The Git tree in use is identified by the current working directory. A
corresponding configuration section needs to be present in the configuration
file (see *[Required Configuration](#required-Configuration)*)

### Configuration file format
The [configparser](https://docs.python.org/3/library/configparser.html) library
is used to parse the configuration file. The general configuration file syntax
is:
```
[<section>]
    <key> = <value>
```

### Required Configuration
Section `user`:
*   `name`: User name
*   `email`: User email address

Section `<tree>`:
*    `url`: Web URL for \<tree>

## Usage
```bash
push.py [<options>] <rev_start>
```
For a full list of options run
```bash
push.py --help
```
