class BuildException(Exception):
    """Exception is raised when target project for profiler is not built"""
    def __init__(self, message):
        super().__init__(message)
