from cx_Freeze import setup, Executable

setup(
    name = "PaperNetwork_Server",
    version = "0.1",
    description = "PaperNetwork - Server",
    executables = [Executable("server.py")],
)