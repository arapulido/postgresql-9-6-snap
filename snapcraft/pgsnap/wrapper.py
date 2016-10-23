import configparser
from glob import glob
import os
import subprocess
import stat
import sys
from textwrap import dedent
import time


PGDATA = os.path.join(os.environ['SNAP_COMMON'], 'data')
PGBIN = os.path.join(os.environ['SNAP'], 'pgsql', 'bin')
PGLIB = os.path.join(os.environ['SNAP'], 'pgsql', 'lib')
PGRUN = os.path.join(os.environ['SNAP_COMMON'], 'run')
PGLOG = os.path.join(os.environ['SNAP_COMMON'], 'log')
PGCONF = os.path.join(PGDATA, 'postgresql.conf')
SNAPCONF = os.path.join(PGDATA, 'snappy.conf')

SNAPINI = os.path.join(os.environ['SNAP_COMMON'], 'snap.ini')

EUID = 1  # daemon
EGID = 1  # daemon


def setuid():
    '''PostgreSQL refuses to run as root

    Drop privileges to a different user, guaranteed to exist,
    until snappy gives us the ability to create users inside
    snap containment.
    '''
    os.setgid(EGID)
    os.setuid(EUID)


def setenv():
    env = os.environ
    snap = env['SNAP']
    env['PGDATA'] = PGDATA
    env['LOCPATH'] = os.path.join(snap, 'usr', 'lib', 'locale')
    env['PATH'] = '{}:{}'.format(PGBIN, env['PATH'])
    env['LD_LIBRARY_PATH'] = '{}:{}'.format(PGLIB, env['LD_LIBRARY_PATH'])

    # Rather than trying to set the compile time DEFAULT_PGSOCKET_DIR,
    # override the default socket directory at run time. This still isn't
    # ideal, as all Debian applications still expect to find the socket
    # in /var/run/postgresql, but this isn't available to the snap.
    if 'PGHOST' not in env:
        env['PGHOST'] = PGRUN

    # Perl environment for plperl stored procedures.
    p = ['{}/etc/perl'.format(env['SNAP']),
         glob('{}/usr/lib/*/perl/5.*.*'.format(env['SNAP']))[0],
         glob('{}/usr/share/perl/*.*.*'.format(env['SNAP']))[0]]
    env['PERL5LIB'] = ':'.join(p)

    # tcl environment for pltcl stored procedures
    p = glob('{}/usr/share/tcltk/tcl*.*'.format(env['SNAP']))[0]
    env['TCL_LIBRARY'] = p


def init_postgresql_conf():
    open(PGCONF, 'a').write(dedent('''
        include = '{}'  # Required for snap packaging
        ''').format(SNAPCONF))


def update_snappy_conf():
    config = dedent('''\
        # Maintained by snap packaging
        #
        unix_socket_directories = '{PGRUN}'
        logging_collector = on
        log_directory = '{PGLOG}'
        external_pid_file = '{PGRUN}/postgres.pid'
        cluster_name = 'snap'
        '''.format(PGRUN=PGRUN, PGLOG=PGLOG))
    if not (os.path.exists(SNAPCONF) and
            open(SNAPCONF, 'r').read() == config):
        open(SNAPCONF, 'w').write(config)
        os.chmod(SNAPCONF, 0o644)


def exec_postgres():
    '''Entry point to launch a PostgreSQL server in the snap.

    We don't background it to give systemd/snapd the most control.
    In particular, we want to know if startup failed. You could use
    pg_ctl with the -w option for this, but startup times vary
    greatly depending on the size of the database and if it was shutdown
    cleanly.
    '''
    setenv()

    if not os.path.isdir(PGRUN):
        os.mkdir(PGRUN, 0o755)
        os.chown(PGRUN, EUID, EGID)

    if not os.path.isdir(PGLOG):
        # Directory can be open, because log file permissions
        # are controlled by postgresql.conf
        os.mkdir(PGLOG, 0o755)
        os.chown(PGLOG, EUID, EGID)

    if not os.path.isdir(PGDATA):
        os.mkdir(PGDATA, 0o700)
        os.chown(PGDATA, EUID, EGID)

    # Bug #1617314. For now, we patch.
    # setuid()  # Change to non-root so initdb and PostgreSQL will run.

    if not os.path.exists(PGCONF):
        subprocess.check_call(['initdb', '--encoding=UTF8', '--locale=C',
                               '--data-checksums', '--username=postgres'])
        init_postgresql_conf()

    update_snappy_conf()

    # Start the server. We do this in the foreground to cope with
    # slow startup times while letting systemd know if it dies.
    sys.stdout.flush()
    sys.stderr.flush()
    cmd = os.path.join(PGBIN, 'postgres')
    os.execlp(cmd, cmd, '-D', PGDATA)


def exec_standard():
    '''General purpose wrapper'''
    setenv()
    cmd = os.path.join(PGBIN, os.path.basename(sys.argv[0]))
    os.execlp(cmd, *sys.argv)


def exec_bash():
    '''Start a bash shell with the customized environment'''
    setenv()
    cmd = os.path.join(os.environ['SNAP'], 'bin', 'bash')
    os.execlp(cmd, *sys.argv)


def get_config():
    config = configparser.ConfigParser()
    if os.path.exists(SNAPINI):
        config.read_file(open(SNAPINI, 'r'), SNAPINI)
        update = False
    else:
        update = True

    if 'logrotate' not in config:
        config['logrotate'] = {}
        update = True

    if 'keep_days' not in config['logrotate']:
        config['logrotate']['keep_days'] = '7'
        update = True

    if update:
        config.write(open(SNAPINI, 'w'))

    return config


def logrotate(config):
    days = int(config['keep_days'])
    if days == 0:
        print('Not removing log files from {}'.format(PGLOG))
        return
    if not os.path.isdir(PGLOG):
        print('Cannot find log directory {}'.format(PGLOG))
        return
    since = time.time() - (days * 24 * 60 * 60)
    print('Removing log files older than {} days from {}'.format(days, PGLOG))
    for dirpath, dirnames, filenames in os.walk(PGLOG):
        for name in filenames:
            path = os.path.join(dirpath, name)
            s = os.lstat(path)
            if stat.S_ISREG(s.st_mode) and s.st_mtime < since:
                print('Removing {}'.format(path))
                os.remove(path)


def do_logrotate():
    while True:
        config = get_config()['logrotate']
        logrotate(config)
        sys.stdout.flush()
        time.sleep(int(config.get('sleep', 3600)))
