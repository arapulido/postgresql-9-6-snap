import snapcraft


class PostgreSQLPlugin(snapcraft.BasePlugin):

    def __init__(self, name, options, project):
        super().__init__(name, options, project)
        self.build_packages.extend(['build-essential'])

    @classmethod
    def schema(cls):
        schema = super().schema()
        schema['properties']['configflags'] = dict(
            type='array', minitems=1, uniqueItems=True,
            items=dict(type='string'), default=[],
        )
        schema['properties']['check'] = dict(type='boolean', default=True)
        schema['properties']['patches'] = dict(
            type='array', minitems=1, uniqueItems=True,
            items=dict(type='string'), default=[],
        )
        schema['build-properties'].append('configflags')
        return schema

    def build(self):
        super().build()

        for patch in self.options.patches:
            patch_cmd = ['patch', '-p1', '--input', patch]
            self.run(patch_cmd)

        configure_cmd = ['./configure', '--prefix=', 'CFLAGS=-DSNAPPY=1']
        configure_cmd.extend(self.options.configflags)
        self.run(configure_cmd)

        build_cmd = ['make', 'world', '-j{}'.format(self.parallel_build_count)]
        self.run(build_cmd)

        if self.options.check:
            check_cmd = ['make', 'check-world', '-j1']  # parallel fails
            self.run(check_cmd)

        install_cmd = ['make', 'install-world',
                       'DESTDIR={}/pgsql'.format(self.installdir)]
        self.run(install_cmd)

    def snap_fileset(self):
        # Cargo-culted from snapcraft.plugins.autotools. May not be required.
        fileset = super().snap_fileset()
        # Remove .la files which don't work when they are moved around
        fileset.append('-**/*.la')
        return fileset
