import shlex
import click
import subprocess
import perun.profile.factory as profile_factory


def run_call_graph():
    find_command = "find . -type f -name '*.ts'"
    find_process = subprocess.Popen(find_command, stdout=subprocess.PIPE, shell=True)
    ts_files, _ = find_process.communicate()
    ts_files = ts_files.decode().strip().split("\n")

    printf_command = "printf 'y\n'"
    npx_tcg_command = f"npx tcg {' '.join(shlex.quote(file) for file in ts_files)}"

    process_printf = subprocess.Popen(printf_command, stdout=subprocess.PIPE, shell=True)
    subprocess.Popen(npx_tcg_command, stdin=process_printf.stdout, shell=True)


@click.command()
@click.option(
    "--filename",
    "-f",
    default="web",
    required=False,
    help="Outputs the graph to the file specified by filename.",
)
@profile_factory.pass_profile
def web(profile: profile_factory.Profile, filename: str) -> None:
    """Graphs visualizing metrics collected by web collector.
    """

    data = profile._storage.get('resources')

    # run_call_graph()
