#!/usr/bin/env python3

import argparse
import configparser
import os
import pygit2
import re
import subprocess
import sys
import time
from email import charset
from email.mime.text import MIMEText
from email.header import Header

re_email = re.compile(r"<([^@]+@[^@]+\.[^@]+)>")

def make_email(repo, commit, tree_name, branch, subject):
    diff = repo.diff(str(commit.parent_ids[0]), str(commit.oid))

    msg = '''
This is a note to let you know that I've just added the patch titled

    {subject}

to my {tree} Git tree which can be found at
    {url}
in the {branch} branch.

Commit-ID:  {sha}
Author:     {authorname} <{authormail}>
AuthorDate: {adate}
Commiter:   {committername} <{committermail}>
ComitDate:  {cdate}
URL:        {url}/commit/{sha}

{cmsg}
---
{diffstats}

{patch}
'''.format(subject=subject, tree=tree_name, url=config[tree_name]['url'], sha=commit.oid,
           authorname=commit.author.name, authormail=commit.author.email,
           adate=time.strftime('%F %T %z', time.localtime(commit.author.time)),
           committername=commit.committer.name, committermail=commit.committer.email,
           cdate=time.strftime('%F %T %z', time.localtime(commit.committer.time)),
           cmsg=commit.message.rstrip(), patch=diff.patch.rstrip(), branch=branch,
           diffstats=diff.stats.format(pygit2.GIT_DIFF_STATS_FULL, 74).rstrip())

    return msg

# define and parse command line arguments
parser = argparse.ArgumentParser(description = "Git push helper")
parser.add_argument('rev_start', metavar="<rev_start>", help="start revision")
parser.add_argument('rev_end', metavar="<rev_end>", nargs='?', default='HEAD', help="end revision")
parser.add_argument('--repo', '-repo', action='append', dest='remote', help="remote repository(s) to push to")
parser.add_argument('--branch', '-branch', help="branch to push to")
parser.add_argument('--dry-run', '-dry-run', action='store_true', default=False, help="do not actually push or notify")
parser.add_argument('--config', '-config', default='~/.pushrc', help="config file (~/.pushrc)")
parser.add_argument('--verbose', '-verbose', action='count', default=0, help="increase verbosity")
parser.add_argument('--force', '-force', action='count', default=0, help="force push")
parser.add_argument('--debug', '-debug', action='store_true', default=False, help="enable debug messages")
args = parser.parse_args()

if args.debug:
    SHA_LEN = -1
    print("Arguments:", file=sys.stderr)
    print("  dry-run: {}".format(args.dry_run), file=sys.stderr)
    print("  verbose: {}".format(args.verbose), file=sys.stderr)
    print("  remote: {}".format(args.remote), file=sys.stderr)
    print("  branch: {}".format(args.branch), file=sys.stderr)
    print("  rev_start: {}".format(args.rev_start), file=sys.stderr)
    print("  rev_end: {}".format(args.rev_end), file=sys.stderr)

# parse config file
config = configparser.ConfigParser()
config.read(os.path.expanduser(args.config))

if args.dry_run:
    print("Dry-run: Not sending email. Not pushing any revs.")

if not config.has_option('user', 'name'):
    raise ValueError("identity not configured. attribute '{}' missing".format('name'))
from_name = config.get('user', 'name')

if not config.has_option('user', 'email'):
    raise ValueError("identity not configured. attribute '{}' missing".format('email'))
from_email = config.get('user', 'email')

tree_name = os.path.basename(os.getcwd())
if tree_name.endswith('.git'):
    tree_name = tree_name[:-4]

if not config.has_option(tree_name, 'url'):
    raise ValueError("URL for tree '{}' not specified".format(tree_name))

if args.branch:
    destination_branch = args.branch
else:
    destination_branch = config.get(tree_name, 'branch', fallback='master')

if args.force == 1 and destination_branch == 'master':
    raise ValueError("force push to master branch not allowed")

if not args.debug:
    SHA_LEN = config.getint('core', 'abbrev', fallback=12)

if args.debug or args.verbose:
    print("tree URL: {}".format(config[tree_name]['url']), file=sys.stderr)

if not args.remote:
    if config.has_option(tree_name, 'remotes'):
        args.remote = config.get(tree_name, 'remotes').split()
    else:
        args.remote = ['origin']

# open the Git repo
repo = pygit2.Repository(pygit2.discover_repository(os.getcwd()))
if args.debug:
    print(repo, file=sys.stderr)

# get revision range to process
rev_start = repo.revparse_single(args.rev_start)
rev_end = repo.revparse_single(args.rev_end)
if args.debug or args.verbose:
    print("rev_start: {}".format(rev_start.oid), file=sys.stderr)
    print("rev_end:   {}".format(rev_end.oid), file=sys.stderr)

revlist = repo.walk(rev_end.oid, pygit2.GIT_SORT_TOPOLOGICAL | pygit2.GIT_SORT_REVERSE)
revlist.hide(rev_start.oid)

# Push to remotes
# (can't figure out how to do this using pygit2)
for remote in args.remote:
    push_cmd = ["git", "push", remote, str(rev_end.oid) + ":" + destination_branch]
    if args.force:
        push_cmd.append('--force')

    if not args.dry_run:
        subprocess.run(push_cmd, check=True)
    else:
        print("Dry-run: Would push: {}".format(" ".join(push_cmd)))

# Acknowledge each commit by email
charset.add_charset('utf-8', charset.QP, charset.QP, 'utf-8')
commit = None
for commit in revlist:
    subject = commit.message.split('\n', 1)[0]
    body = make_email(repo, commit, tree_name, destination_branch, subject)
    if args.debug:
        print(body)

    to = [commit.author.email]
    for line in commit.message.split('\n'):
        m = re_email.search(line);
        if m and  m.groups:
            to.append(m.groups()[0])

    # convert to set which removes dups too
    to = set(to)
    if args.debug:
        print("To: ", to)

    msg = MIMEText(body.encode('utf-8'), 'plain', 'utf-8')
    msg["From"] = Header("{}".format(from_name), "utf-8")
    msg["From"].append(" <{}>".format(from_email), 'us-ascii')
    msg["Subject"] = Header('patch "{}" added to {}'.format(subject, tree_name), "utf-8")
    msg["To"] = Header(", ".join(to), "us-ascii")

    if args.debug or args.verbose > 1:
        print(msg.as_bytes().decode(encoding='utf-8'))

    if not args.dry_run:
        p = subprocess.Popen(["msmtp", "-t", "-oi"], stdin=subprocess.PIPE)
        p.communicate(bytes(msg.as_bytes().decode(encoding="utf-8"), "utf-8"))

    print("Acknowledged: {} \"{}\"".format(str(commit.oid)[:SHA_LEN], subject))

if not commit:
    print("Empty commit range. Exiting")
    sys.exit(0)
