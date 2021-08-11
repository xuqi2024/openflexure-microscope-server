import argparse
import os
import subprocess

def download_webapp_from_CI():
    """Download a pre-built archive of the web app.
    
    This (ab)uses GitLab's mechanism of retrieving artifacts, and should
    allow you to retrieve the latest build of the Vue web app.  Hopefully,
    this will save you needing to compile it from source on a Pi too 
    often.
    """
    parser = argparse.ArgumentParser(description="Download static web app from GitLab CI")
    parser.add_argument("branch", default="master")
    args = parser.parse_args()

    # We want to make sure the command is run at the root of this repository
    # so we take the parent of the current file
    repo_dir = os.path.realpath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    if not os.path.isdir(os.path.join(repo_dir, "openflexure_microscope", "api", "static")):
        print("Couldn't determine the right place to put static files")
        print(f"We think the repository should be at {repo_dir}.")
        exit(-1)

    branch = args.branch
    url = (
        "https://gitlab.com/openflexure/openflexure-microscope-server/"
        f"-/jobs/artifacts/{branch}/raw/"
        f"dist/openflexure-microscope-webapp-{branch}.tar.gz?job=package"
    )
    cmd = f"curl -L {url} | tar -xz"
    print(f"cd {repo_dir}")
    print(cmd)
    subprocess.call(cmd, shell=True, cwd=repo_dir)