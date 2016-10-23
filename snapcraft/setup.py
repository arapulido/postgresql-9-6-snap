import os
from setuptools import setup, find_packages

# Generate an entry point for every PostgreSQL tool we need to wrap.
# Staging directory isn't exported directly, so calculate it indirectly.
bindir = [d for d in os.environ['PATH'].split(':')
          if d.endswith('/stage/bin')][0]
stagedir = os.path.abspath(os.path.join(bindir, os.pardir))
pgbindir = os.path.join(stagedir, 'pgsql', 'bin')
standard_commands = os.listdir(pgbindir)

console_scripts = (['run_postgresql=pgsnap.wrapper:exec_postgres',
                    'run_logrotate=pgsnap.wrapper:do_logrotate',
                    'run_bash=pgsnap.wrapper:exec_bash'] +
                   ['{}=pgsnap.wrapper:exec_standard'.format(cmd)
                    for cmd in standard_commands])

setup(name='pgsnap',
      version='1.0.0',
      packages=find_packages(),
      entry_points=dict(console_scripts=console_scripts))
