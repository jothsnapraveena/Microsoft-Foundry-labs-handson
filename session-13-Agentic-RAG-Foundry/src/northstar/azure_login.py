"""Azure sign-in through the Azure CLI login, with a readable failure."""
import os
from pathlib import Path
import shutil

# Where the Windows installer puts the CLI. A terminal opened before the install does not have it on PATH.
DEFAULT_CLI_DIRS = (r"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin", r"C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\wbin")
SIGN_IN_HELP = ("Could not sign in to Azure. Install the Azure CLI if needed, run 'az login', and choose the "
                "subscription that holds your resources. See docs/azure-setup.md, step 1.")


class SignInError(Exception):
    pass


def find_azure_cli():
    """Make 'az' reachable for this process when it is installed but missing from PATH."""
    if shutil.which("az"):
        return True
    for directory in DEFAULT_CLI_DIRS:
        if Path(directory, "az.cmd").exists():
            os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + directory
            return True
    return False


def azure_credential():
    from azure.identity import DefaultAzureCredential
    find_azure_cli()
    return DefaultAzureCredential()


def explain(error):
    """Turn an Azure authentication failure into one actionable line; re-raise anything else."""
    from azure.core.exceptions import ClientAuthenticationError
    if isinstance(error, ClientAuthenticationError):
        detail = "The Azure CLI is not installed." if not find_azure_cli() else "The Azure CLI is installed but not signed in, or the login expired."
        raise SignInError(f"{SIGN_IN_HELP}\n{detail}") from None
    raise error
