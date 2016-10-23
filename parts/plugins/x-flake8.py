import snapcraft


class Flake8Plugin(snapcraft.BasePlugin):
    def __init__(self, name, options, project):
        super().__init__(name, options, project)
        self.build_packages.extend(['flake8', 'python3-flake8'])

    def build(self):
        super().build()
        cmd = ['flake8', '.']
        self.run(cmd)

    def snap_fileset(self):
        fileset = super().snap_fileset()
        fileset.append('-**')
        return fileset
