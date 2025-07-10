# Zenodo archiving
This folder contains some scripts put together by Kaspar Bumke, and reused by Richard, to upload the contents of the repository, together with any CI build artefacts, to Zenodo.  The result is a link, taking you to a pre-populated upload on Zenodo that you can manually correct and upload.  In order to customise it for a new project, there are a few steps you need, outlined below.

## Setting up archival
* Copy this folder to `scripts/zenodo` in your repository.
* Customise `metadata.yaml` (in this folder) with the metadata you want to be attached to your uploads.  Zenodo provide [documentation](https://developers.zenodo.org/#deposit-metadata) on the contents of this file, but hopefully the one here will be a useful start.
* Add a CI job to `.gitlab-ci.yml` at the top level of your repository.  The one in this repository should serve as an example.  This requires you to add a couple of places:
  - Ensure you have a "stage" called "deploy" that runs after you've built anything you will want to archive.  This is the last stage by default, but if you have a custom list of stages, it is usually found at the top of the file.  For example:
    ```yaml
    stages:
    - analysis
    - testing
    - build
    - package
    - deploy
    ```
  - Copy and paste the block below, to build and upload the source and built artefacts.
    ```yaml
    zenodo:
    stage: deploy
    image: ubuntu:20.04
    before_script:
        - apt-get update -qq
        - apt-get -y -qq install git python3-pip
        - pip3 install -r scripts/zenodo/requirements.txt
    variables:
        ZENODO_USE_SANDBOX: "true"
    script:
        - git archive "${CI_COMMIT_REF_NAME}" --format=zip --output="${CI_PROJECT_NAME}-${CI_COMMIT_REF_NAME}-source.zip"
        - python3 scripts/zenodo/upload_to_zenodo.py "${CI_PROJECT_NAME}-${CI_COMMIT_REF_NAME}-source.zip" dist/*
    artifacts:
        # this is only a small html link, let's just keep it forever
        # gitlab doesn't understand "expire_in: never" yet though
        expire_in: 100000 years
        name: zenodo-${CI_PROJECT_NAME}-${CI_COMMIT_REF_NAME}-link.html
        paths:
        - zenodo-link.html
    only:
        - tags
        - web
    ```
  - Customise the lines that create archives or specify files for upload.  As a minimum, you will need to customise the list of files to upload.  The block above will upload everything in the `dist/` folder, which is populated with archives produced in previous CI jobs.  If you don't have any other CI jobs, you can just delete the `dist/*` from the end of the relevant line, and the script will upload an archive of the source code only.
  - **Note: LFS files are not included in the source archive.** If you use LFS, you may want to make the source archive manually in CI, so that LFS files are downloaded and included.  If you don't know what LFS is, you can probably ignore this.  If you look at your upload, and there are lots of files that should be large, and are actually less than 200 bytes, you probably do have LFS enabled.
* Generate a Zenodo access token.  There are instructions in the [Zenodo documentation](https://developers.zenodo.org/#authentication), but in brief you must first log in to Zenodo and [generate an access token](https://zenodo.org/account/settings/applications/tokens/new/).  If you want to try it out using the "sandbox" before uploading to Zenodo proper, you can do the same thing with the [sandbox site](https://sandbox.zenodo.org/account/settings/applications/tokens/new/).  You need to tick `deposit:write` on the token's permissions.
* Paste your Zenodo access token into a [GitLab CI variable](https://docs.gitlab.com/ee/ci/variables/#add-a-cicd-variable-to-a-project) called `ZENODO_API_KEY_REAL`, and paste the sandbox access token into another variable called `ZENODO_API_KEY_SANDBOX`.
