# Unreleased

## Developer changes
* CI now builds and tests on a simulated Raspberry Pi, using our own image. ([!156](https://gitlab.com/openflexure/openflexure-microscope-server/-/merge_requests/156))

# [v2.11.0](https://gitlab.com/openflexure/openflexure-microscope-server/compare/v2.10.1...v2.11.0) (2022-08-08)

## New features
* Background detection can now be used in scans, if you have the background-detect extension. ([!153](https://gitlab.com/openflexure/openflexure-microscope-server/-/merge_requests/153))
* Support for Sangaboard firmware v1, via updated `sangaboard` dependency ([!154](https://gitlab.com/openflexure/openflexure-microscope-server/-/merge_requests/154))

## Bug fixes
* Fixed links in the OpenAPI documentation describing actions etc. ([!155](https://gitlab.com/openflexure/openflexure-microscope-server/-/merge_requests/154))

# [v2.10.1](https://gitlab.com/openflexure/openflexure-microscope-server/compare/v2.10.0...v2.10.1) (2022-01-17)
## Bug fixes
* Fixed a typo in the serialisation of numpy arrays (#243) ([!148](https://gitlab.com/openflexure/openflexure-microscope-server/-/merge_requests/148))
* Made it possible again to track sharpness while the stage is not moving.  This changed when the extra thread was removed from `JPEGSharpnessMonitor`. ([!149](https://gitlab.com/openflexure/openflexure-microscope-server/-/merge_requests/149))

## Minor improvements
* Added a function to measure settling time after a Z move ([!149](https://gitlab.com/openflexure/openflexure-microscope-server/-/merge_requests/149))
* Bumped some INFO logging statements to DEBUG to de-clutter the logs. ([!151](https://gitlab.com/openflexure/openflexure-microscope-server/-/merge_requests/149))

# [v2.10.0](https://gitlab.com/openflexure/openflexure-microscope-server/compare/v2.10.0b2...v2.10.0) (2021-08-11)
## Documentation improvements
* Many improvements to the generated OpenAPI documentation, resulting in it now validating. ([!133](https://gitlab.com/openflexure/openflexure-microscope-server/-/merge_requests/133))
* Added a user guide and fixed readthedocs.  Linked to the API documentation, and store it on the build server with releases. ([!140](https://gitlab.com/openflexure/openflexure-microscope-server/-/merge_requests/140))

## Developer changes
* The web app is now in a top-level directory ([!122]((https://gitlab.com/openflexure/openflexure-microscope-server/-/merge_requests/122))
* OpenAPI descriptions are now easier to download from a merge request. ([!139](https://gitlab.com/openflexure/openflexure-microscope-server/-/merge_requests/139))

## Minor bug fixes and improvements
* Removed vestigial error handling code that is now dealt with by LabThings. ([!137](https://gitlab.com/openflexure/openflexure-microscope-server/-/merge_requests/137))
* taskSubmitter buttons in the web app now handle errors more robustly.  This fixes a bug where the progress bar would spin indefinitely.  ([!138](https://gitlab.com/openflexure/openflexure-microscope-server/-/merge_requests/138))
* Smart stack controls now only appear if the plugin is installed.  ([!142](https://gitlab.com/openflexure/openflexure-microscope-server/-/merge_requests/142))
* Javascript dependencies are updated for security.  ([!141](https://gitlab.com/openflexure/openflexure-microscope-server/-/merge_requests/141))

# [v2.10.0b2](https://gitlab.com/openflexure/openflexure-microscope-server/compare/v2.10.0b1...v2.10.0b2) (2021-08-11)
## New features
* Added support for ImJoy plugins ([!120](https://gitlab.com/openflexure/openflexure-microscope-server/-/merge_requests/120))
* Added a setting to disable the gallery ([!120](https://gitlab.com/openflexure/openflexure-microscope-server/-/merge_requests/120))
* Scan parameters are now remembered in the "capture" pane ([!132](https://gitlab.com/openflexure/openflexure-microscope-server/-/merge_requests/132))
* The Capture pane now contains controls for the smart stack plugin, if installed (([!134](https://gitlab.com/openflexure/openflexure-microscope-server/-/merge_requests/134)))

## Developer changes
* CI now fails if `Pipfile.lock` is out of date ([!131](https://gitlab.com/openflexure/openflexure-microscope-server/-/merge_requests/131))
* The Thing Description and OpenAPI documentation are now valid, and much improved ([!133](https://gitlab.com/openflexure/openflexure-microscope-server/-/merge_requests/133))
* Pytest XML reports are now recorded in the CI pipeline ([!135](https://gitlab.com/openflexure/openflexure-microscope-server/-/merge_requests/135))
* The application is now packaged for every commit on `master` ([!136](https://gitlab.com/openflexure/openflexure-microscope-server/-/merge_requests/136))

# [v2.10.0b0](https://gitlab.com/openflexure/openflexure-microscope-server/compare/v2.10.0b0...v2.10.0b1) (2021-05-26)
## Minor bug fixes and improvements
* Fixed some installation issues with updated Python dependencies ([!129](https://gitlab.com/openflexure/openflexure-microscope-server/-/merge_requests/129))

# [v2.10.0b0](https://gitlab.com/openflexure/openflexure-microscope-server/compare/v2.9.3...v2.10.0b0) (2021-05-18)

## New features
* Improved auto gain, white balance, and lens shading table correction (!119).  Fixes #191.
  The old auto calibration code has been replaced by a slower, more manual method that is more reliable.
  Individual parts of the calibration can be run independently (auto gain/exposure, auto white balance, lens shading).
  This should also improve the experience when using e.g. fluorescence imaging modes.

## Developer changes
* Build instructions were updated (!115)
* We've switched from `poetry` to `pipenv` to solve dependency management issues on the Raspberry Pi (!124).  See the updated 
  repository README for a full breakdown of what configuration information goes where.  Closes #218.
* Improved handling of stream settings and origin override (!125, !116, !117)
  This fixes a longstanding irritation when developing on localhost using `npm run serve`, where it was necessary to
  enter the API origin address every time the page was refreshed, and then manually re-enable the web stream.  Both
  these issues are now fixed.
  * The API origin override field in the "dev tools" pane now remembers its value
  * The API origin can be overridden using the URL
  * Stream settings are now remembered in local storage

## Minor bug fixes and improvements
* Better error handling for picamerax (!86)
* Add coverage report to mypy (!110)
* `MissingStage` can now be explicitly selected in microscope configuration (!112)
* The first-run "tour" placement is improved and shouldn't block the interface any more (!114)
  * Fix placement of tour messages for icons ([afbb716](https://gitlab.com/openflexure/openflexure-microscope-server/commit/afbb716))
  * This closes #199 and helps with #193
* The IHI interface now explicitly states scan style should be raster (!113)
* Absolute moves are now fixed (!126), closing #220, #221, and #222.
* Fixed a typing error with the camera stage mapping matrix and `numpy` 1.20 (!127).
* Scans now have a minimum dimension of 1 in each axis, which avoids dividing by zero (!123)


# [v2.9.3](https://gitlab.com/openflexure/openflexure-microscope-server/compare/v2.9.2...v2.9.3) (2020-12-14)

- Fix #194 ([0592d31](https://gitlab.com/openflexure/openflexure-microscope-server/commit/0592d31)), closes [#194](https://gitlab.com/openflexure/openflexure-microscope-server/issues/194)

# [v2.9.2](https://gitlab.com/openflexure/openflexure-microscope-server/compare/v2.9.1...v2.9.2) (2020-12-09)

- Added more Advanced bitrate controls ([d2488c5](https://gitlab.com/openflexure/openflexure-microscope-server/commit/d2488c5))
- Watch for broken frames using JPEG end bytes, and log error ([6838038](https://gitlab.com/openflexure/openflexure-microscope-server/commit/6838038))

# [v2.9.1](https://gitlab.com/openflexure/openflexure-microscope-server/compare/v2.9.0...v2.9.1) (2020-12-07)

- Server: Added mjpeg bitrate to settings ([3e2f876](https://gitlab.com/openflexure/openflexure-microscope-server/commit/3e2f876))
- JS Client: Replaced MJPEG quality setting with MJPEG bitrate ([42e0dfd](https://gitlab.com/openflexure/openflexure-microscope-server/commit/42e0dfd))

# [v2.9.0](https://gitlab.com/openflexure/openflexure-microscope-server/compare/v2.8.0...v2.9.0) (2020-12-07)

## Developer changes

### Extension loader

- **Updated default extensions to subclass structure ([8d0759e](https://gitlab.com/openflexure/openflexure-microscope-server/commit/8d0759e))**
  - Updated documentation to subclass-based extensions ([bacc111](https://gitlab.com/openflexure/openflexure-microscope-server/commit/bacc111))
  - Added type information to LABTHINGS_EXTENSIONS ([b8354d3](https://gitlab.com/openflexure/openflexure-microscope-server/commit/b8354d3))
  - Clarified LABTHINGS_EXTENSIONS in docs ([f849afd](https://gitlab.com/openflexure/openflexure-microscope-server/commit/f849afd))

### Testing

- Added basic unit tests of non-integrated functions ([5137d1b](https://gitlab.com/openflexure/openflexure-microscope-server/commit/5137d1b))

### Static analysis

- Added extra type hints ([7ba3f44](https://gitlab.com/openflexure/openflexure-microscope-server/commit/7ba3f44))
- Added numpy types ([63b633b](https://gitlab.com/openflexure/openflexure-microscope-server/commit/63b633b))
- Added type hints to CSM extension ([311366c](https://gitlab.com/openflexure/openflexure-microscope-server/commit/311366c))
- Fixed types in move_rel method ([ac667c3](https://gitlab.com/openflexure/openflexure-microscope-server/commit/ac667c3))
- Static type analysis ([7866ec0](https://gitlab.com/openflexure/openflexure-microscope-server/commit/7866ec0))
- Stricter runtime type checks ([f2a2d88](https://gitlab.com/openflexure/openflexure-microscope-server/commit/f2a2d88))

### Documentation

- Added better developer notes ([a3b1b8a](https://gitlab.com/openflexure/openflexure-microscope-server/commit/a3b1b8a))
- Added changelog generator ([de6dbe4](https://gitlab.com/openflexure/openflexure-microscope-server/commit/de6dbe4))

### CI/CD

- Added eslint and cache to CI ([f5012cd](https://gitlab.com/openflexure/openflexure-microscope-server/commit/f5012cd))
- Added job explanation comments ([c1e17de](https://gitlab.com/openflexure/openflexure-microscope-server/commit/c1e17de))
- Added poetry to script environment ([3814e7d](https://gitlab.com/openflexure/openflexure-microscope-server/commit/3814e7d))
- Allow code quality jobs to retry ([f15a5c7](https://gitlab.com/openflexure/openflexure-microscope-server/commit/f15a5c7))
- Fixed JS artifact path ([3a90a42](https://gitlab.com/openflexure/openflexure-microscope-server/commit/3a90a42))

## API functionality

- Added API route to convert LST to PNG ([4d40e81](https://gitlab.com/openflexure/openflexure-microscope-server/commit/4d40e81))

## JS Client

### New functionality

- Added log level filter ([4d1d0a1](https://gitlab.com/openflexure/openflexure-microscope-server/commit/4d1d0a1))
- Added options to invert navigation steps ([d49b34e](https://gitlab.com/openflexure/openflexure-microscope-server/commit/d49b34e))
- Added backlash and settle time settings ([c0fcd22](https://gitlab.com/openflexure/openflexure-microscope-server/commit/c0fcd22))
- Added stream and capture quality settings ([0f7cecb](https://gitlab.com/openflexure/openflexure-microscope-server/commit/0f7cecb))

### Fixes

- Fixed global state and scrolltotop ([ef9f257](https://gitlab.com/openflexure/openflexure-microscope-server/commit/ef9f257))
- Fixed individual captures creating 'undefined' dataset ([213dec3](https://gitlab.com/openflexure/openflexure-microscope-server/commit/213dec3))
- Fixed onError propagation ([08f6532](https://gitlab.com/openflexure/openflexure-microscope-server/commit/08f6532))
- Fixed onScanError ([1de6b2a](https://gitlab.com/openflexure/openflexure-microscope-server/commit/1de6b2a))
- globalUpdateCaptures after scan ([599c315](https://gitlab.com/openflexure/openflexure-microscope-server/commit/599c315))
- Handle missing this.$refs.textboxKey ref ([9d04842](https://gitlab.com/openflexure/openflexure-microscope-server/commit/9d04842))
- Fixed IHI tab icon duplication bug ([e17366d](https://gitlab.com/openflexure/openflexure-microscope-server/commit/e17366d))

### Design/style

- Added custom h4 formatting ([4ba4403](https://gitlab.com/openflexure/openflexure-microscope-server/commit/4ba4403))
- Rearranged element layout ([455b868](https://gitlab.com/openflexure/openflexure-microscope-server/commit/455b868))
- Rearranged settings and added LST download ([f0a3127](https://gitlab.com/openflexure/openflexure-microscope-server/commit/f0a3127))

### Internal cleanup

- Common watch format ([3e783c5](https://gitlab.com/openflexure/openflexure-microscope-server/commit/3e783c5))
- Removed unneeded plugin:vue/essential ([358d441](https://gitlab.com/openflexure/openflexure-microscope-server/commit/358d441))
- Removed unused webcomponent support ([f187a3a](https://gitlab.com/openflexure/openflexure-microscope-server/commit/f187a3a))
- - Moved backlash settings ([a2f8158](https://gitlab.com/openflexure/openflexure-microscope-server/commit/a2f8158))

## Server

### Features

- Added API route to convert LST to PNG ([4d40e81](https://gitlab.com/openflexure/openflexure-microscope-server/commit/4d40e81))
  - Return LST as a file ([aba3eb3](https://gitlab.com/openflexure/openflexure-microscope-server/commit/aba3eb3))

### Fixes

- Fixed "classic" autofocus 'PiCameraStreamer' object has no attribute 'annotate_text' error ([58b2967](https://gitlab.com/openflexure/openflexure-microscope-server/commit/58b2967))
- Fixed broken dataset rendering if key exists but is empty ([fd42e2e](https://gitlab.com/openflexure/openflexure-microscope-server/commit/fd42e2e))
- Fixed camera settings read ([25d3b15](https://gitlab.com/openflexure/openflexure-microscope-server/commit/25d3b15))
- Fixed get_locations method reference ([d288484](https://gitlab.com/openflexure/openflexure-microscope-server/commit/d288484))
- Fixed SangaDeltaStage type annotations ([9659c45](https://gitlab.com/openflexure/openflexure-microscope-server/commit/9659c45))
- Fixed tile method reference ([18a0eed](https://gitlab.com/openflexure/openflexure-microscope-server/commit/18a0eed))
- Handle missing endpoints ([bc39277](https://gitlab.com/openflexure/openflexure-microscope-server/commit/bc39277))

### Internal API changes

- Deprecated camera `start_worker` and `get_frame` methods
  - Added `start_worker` and `get_frame` aliases for compatibility ([bc9b80d](https://gitlab.com/openflexure/openflexure-microscope-server/commit/bc9b80d))
- Replace top-level actions View with builtin LabThings ([421a2e3](https://gitlab.com/openflexure/openflexure-microscope-server/commit/421a2e3))
- Updated to LabThings 1.2.1 ([249e301](https://gitlab.com/openflexure/openflexure-microscope-server/commit/249e301))

### Internal cleanup

- **Remove separate camera stream thread ([021745d](https://gitlab.com/openflexure/openflexure-microscope-server/commit/021745d))**
- Cleaned up code layout ([da62126](https://gitlab.com/openflexure/openflexure-microscope-server/commit/da62126))
- Cleaned up main app setup ([e464086](https://gitlab.com/openflexure/openflexure-microscope-server/commit/e464086))
- Cleaned up store and removed unused FoV setting ([a1ae947](https://gitlab.com/openflexure/openflexure-microscope-server/commit/a1ae947))
- Code formatting ([dd81640](https://gitlab.com/openflexure/openflexure-microscope-server/commit/dd81640))
- Fixed unused imports ([b2192b2](https://gitlab.com/openflexure/openflexure-microscope-server/commit/b2192b2))
- Integrated CSMExtension ([9203545](https://gitlab.com/openflexure/openflexure-microscope-server/commit/9203545))
- Moved frames_iterator scope ([3058c67](https://gitlab.com/openflexure/openflexure-microscope-server/commit/3058c67))
- Moved gen() into streams.py ([c9c29a7](https://gitlab.com/openflexure/openflexure-microscope-server/commit/c9c29a7))
- Only use CompositeLock for microscope lock ([e433a89](https://gitlab.com/openflexure/openflexure-microscope-server/commit/e433a89))
- Reduced logging level of some mock camera notices ([8eff136](https://gitlab.com/openflexure/openflexure-microscope-server/commit/8eff136))
- Removed old console logs ([2e34722](https://gitlab.com/openflexure/openflexure-microscope-server/commit/2e34722))
- Removed old picamera_lst_path attribute ([85f77fa](https://gitlab.com/openflexure/openflexure-microscope-server/commit/85f77fa))
- Removed pointless abstract method implementations ([6d1f019](https://gitlab.com/openflexure/openflexure-microscope-server/commit/6d1f019))
- Removed unused pynpm package ([6819ded](https://gitlab.com/openflexure/openflexure-microscope-server/commit/6819ded))
- Tweaked deprecation warnings ([a844efc](https://gitlab.com/openflexure/openflexure-microscope-server/commit/a844efc))
- Updated dependencies ([3c3ecd7](https://gitlab.com/openflexure/openflexure-microscope-server/commit/3c3ecd7))

# [v2.8.0](https://gitlab.com/openflexure/openflexure-microscope-server/compare/v2.8.0-beta.3b...v2.8.0) (2020-11-16)

- 2.8.0 ([729f101](https://gitlab.com/openflexure/openflexure-microscope-server/commit/729f101))
- Added documentation comments ([3eb2aa8](https://gitlab.com/openflexure/openflexure-microscope-server/commit/3eb2aa8))
- Added frame iterator explanation comment ([90ccd0b](https://gitlab.com/openflexure/openflexure-microscope-server/commit/90ccd0b))
- Added use_video_port argument back to array() ([f51d4ff](https://gitlab.com/openflexure/openflexure-microscope-server/commit/f51d4ff))
- Move stream frame management into FrameStream class ([f765540](https://gitlab.com/openflexure/openflexure-microscope-server/commit/f765540))

# [v2.8.0-beta.3b](https://gitlab.com/openflexure/openflexure-microscope-server/compare/v2.8.0-beta.3...v2.8.0-beta.3b) (2020-11-13)

- 2.8.0-beta.3 ([73eda10](https://gitlab.com/openflexure/openflexure-microscope-server/commit/73eda10))
- Add pre-commit ([5119e2c](https://gitlab.com/openflexure/openflexure-microscope-server/commit/5119e2c))
- Added full TileScanArgs schema ([3451b8a](https://gitlab.com/openflexure/openflexure-microscope-server/commit/3451b8a))
- Added note on manually running pre-commit ([36e837d](https://gitlab.com/openflexure/openflexure-microscope-server/commit/36e837d))
- Added note on pre-commit ([0647a03](https://gitlab.com/openflexure/openflexure-microscope-server/commit/0647a03))
- Added rescue to Poetry scripts ([1f0b90c](https://gitlab.com/openflexure/openflexure-microscope-server/commit/1f0b90c))
- Cleaned up Capture schemas ([84dcf4f](https://gitlab.com/openflexure/openflexure-microscope-server/commit/84dcf4f))
- Data-driven tab layout ([c645804](https://gitlab.com/openflexure/openflexure-microscope-server/commit/c645804))
- Extra comments ([c48c6d8](https://gitlab.com/openflexure/openflexure-microscope-server/commit/c48c6d8))
- Formatting ([6644819](https://gitlab.com/openflexure/openflexure-microscope-server/commit/6644819))
- Improved args schema for captures ([f681800](https://gitlab.com/openflexure/openflexure-microscope-server/commit/f681800))
- Moved piexif into captures submodule ([7c450b6](https://gitlab.com/openflexure/openflexure-microscope-server/commit/7c450b6))
- Moved PyLint config back to pyproject.toml ([527bfeb](https://gitlab.com/openflexure/openflexure-microscope-server/commit/527bfeb))
- Removed default JSON files and submoduled JSON encoder class ([4a9d1c5](https://gitlab.com/openflexure/openflexure-microscope-server/commit/4a9d1c5))
- Removed duplicated code ([004ba0b](https://gitlab.com/openflexure/openflexure-microscope-server/commit/004ba0b))
- Removed now-redundant TODO comments ([c0f9f34](https://gitlab.com/openflexure/openflexure-microscope-server/commit/c0f9f34))
- Removed old JSONResponse class ([b350f62](https://gitlab.com/openflexure/openflexure-microscope-server/commit/b350f62))
- Removed pre-commit from Poetry dependencies ([00d30d8](https://gitlab.com/openflexure/openflexure-microscope-server/commit/00d30d8))
- Removed PyLint from pre-commit ([cb4afba](https://gitlab.com/openflexure/openflexure-microscope-server/commit/cb4afba))
- Removed unused files from root ([e25c23c](https://gitlab.com/openflexure/openflexure-microscope-server/commit/e25c23c))
- Reverted logging style ([6fb61e1](https://gitlab.com/openflexure/openflexure-microscope-server/commit/6fb61e1))
- Style and linting ([f4b123c](https://gitlab.com/openflexure/openflexure-microscope-server/commit/f4b123c))
- Updated all log strings to new format ([9f52521](https://gitlab.com/openflexure/openflexure-microscope-server/commit/9f52521))
- Updated to LabThings 1.1.3 ([738f527](https://gitlab.com/openflexure/openflexure-microscope-server/commit/738f527))
- Warn about unused settings when updating ([1e273be](https://gitlab.com/openflexure/openflexure-microscope-server/commit/1e273be))

# [v2.8.0-beta.2](https://gitlab.com/openflexure/openflexure-microscope-server/compare/v2.8.0-beta.1...v2.8.0-beta.2) (2020-11-11)

- 2.8.0-beta.2 ([8c180ca](https://gitlab.com/openflexure/openflexure-microscope-server/commit/8c180ca))
- Added submit button to API origin override form ([1e8978d](https://gitlab.com/openflexure/openflexure-microscope-server/commit/1e8978d))
- Fixed tab switcher background height ([3387c27](https://gitlab.com/openflexure/openflexure-microscope-server/commit/3387c27))
- Scroll to top when pagination switches ([fa909db](https://gitlab.com/openflexure/openflexure-microscope-server/commit/fa909db))

# [v2.8.0-beta.1](https://gitlab.com/openflexure/openflexure-microscope-server/compare/v2.8.0-beta.0...v2.8.0-beta.1) (2020-11-09)

- 2.8.0-beta.1 ([64aa565](https://gitlab.com/openflexure/openflexure-microscope-server/commit/64aa565))
- Added capture count warning ([9e887c0](https://gitlab.com/openflexure/openflexure-microscope-server/commit/9e887c0))
- Added classes for error sources ([7043721](https://gitlab.com/openflexure/openflexure-microscope-server/commit/7043721))
- Added internet, RAM, and storage checkers ([5afff59](https://gitlab.com/openflexure/openflexure-microscope-server/commit/5afff59))
- Added newline symbols ([121afb4](https://gitlab.com/openflexure/openflexure-microscope-server/commit/121afb4))
- Added picamera import checker ([013aebd](https://gitlab.com/openflexure/openflexure-microscope-server/commit/013aebd))
- Added platform info to output ([8349b37](https://gitlab.com/openflexure/openflexure-microscope-server/commit/8349b37))
- Added stage tests and tidied up rescue ([0989a50](https://gitlab.com/openflexure/openflexure-microscope-server/commit/0989a50))
- Allow running tasks to be resumed ([ac382b7](https://gitlab.com/openflexure/openflexure-microscope-server/commit/ac382b7))
- Changed default pollInterval to 1s ([5a32e8a](https://gitlab.com/openflexure/openflexure-microscope-server/commit/5a32e8a))
- Changed newline symbols ([061618d](https://gitlab.com/openflexure/openflexure-microscope-server/commit/061618d))
- Changed reload to 60s timeout ([b98522a](https://gitlab.com/openflexure/openflexure-microscope-server/commit/b98522a))
- Fixed duplicated polling timers ([fcd9fa4](https://gitlab.com/openflexure/openflexure-microscope-server/commit/fcd9fa4))
- Fixed GPU preview requests happening regardless of settings ([5feba6a](https://gitlab.com/openflexure/openflexure-microscope-server/commit/5feba6a))
- Fixed ignored kwargs ([eae3124](https://gitlab.com/openflexure/openflexure-microscope-server/commit/eae3124))
- Formatting and linting ([e416563](https://gitlab.com/openflexure/openflexure-microscope-server/commit/e416563))
- Formatting and linting ([cd61ad3](https://gitlab.com/openflexure/openflexure-microscope-server/commit/cd61ad3))
- Reduced long-term lock usage ([4c61f0c](https://gitlab.com/openflexure/openflexure-microscope-server/commit/4c61f0c))
- Removed in-memory full metadata from CaptureObject ([9dab242](https://gitlab.com/openflexure/openflexure-microscope-server/commit/9dab242))
- Removed port scanning warning ([5319beb](https://gitlab.com/openflexure/openflexure-microscope-server/commit/5319beb))
- Removed unused import ([cbea2f5](https://gitlab.com/openflexure/openflexure-microscope-server/commit/cbea2f5))
- Removed unused output ([471ee5e](https://gitlab.com/openflexure/openflexure-microscope-server/commit/471ee5e))
- Style and linting ([de135ab](https://gitlab.com/openflexure/openflexure-microscope-server/commit/de135ab))
- Support tuple-split strings as error messages ([f12671f](https://gitlab.com/openflexure/openflexure-microscope-server/commit/f12671f))
- Tidied up logging ([06fb81e](https://gitlab.com/openflexure/openflexure-microscope-server/commit/06fb81e))
- Upped capture count warning to 10000 ([0647acd](https://gitlab.com/openflexure/openflexure-microscope-server/commit/0647acd))

# [v2.8.0-beta.0](https://gitlab.com/openflexure/openflexure-microscope-server/compare/v2.7.0...v2.8.0-beta.0) (2020-11-03)

- 2.8.0-beta.0 ([368f86c](https://gitlab.com/openflexure/openflexure-microscope-server/commit/368f86c))
- Fixed reloading timestamp in new format ([86732b8](https://gitlab.com/openflexure/openflexure-microscope-server/commit/86732b8))
- Formatting ([32cf2de](https://gitlab.com/openflexure/openflexure-microscope-server/commit/32cf2de))
- Removed full capture metadata from top-level resource list ([b69c903](https://gitlab.com/openflexure/openflexure-microscope-server/commit/b69c903))
- Simplified build_captures_from_exif ([6c51da5](https://gitlab.com/openflexure/openflexure-microscope-server/commit/6c51da5))
- Updated client to simplify capture data ([982154c](https://gitlab.com/openflexure/openflexure-microscope-server/commit/982154c))

# [v2.7.0](https://gitlab.com/openflexure/openflexure-microscope-server/compare/v2.6.5...v2.7.0) (2020-10-30)

- 2.7.0 ([c58827a](https://gitlab.com/openflexure/openflexure-microscope-server/commit/c58827a))
- Add header to put request to ensure string is sent ([97ff8d4](https://gitlab.com/openflexure/openflexure-microscope-server/commit/97ff8d4))
- Added API LogFileView ([f1d0ea5](https://gitlab.com/openflexure/openflexure-microscope-server/commit/f1d0ea5))
- Added download attribute to log file downloader ([3ba9718](https://gitlab.com/openflexure/openflexure-microscope-server/commit/3ba9718))
- Added extra divider ([46120ea](https://gitlab.com/openflexure/openflexure-microscope-server/commit/46120ea))
- Added logger tab ([21b150b](https://gitlab.com/openflexure/openflexure-microscope-server/commit/21b150b))
- Added pagination to gallery ([e1cca30](https://gitlab.com/openflexure/openflexure-microscope-server/commit/e1cca30))
- Always use builtin JPEG thumbnails ([10d264c](https://gitlab.com/openflexure/openflexure-microscope-server/commit/10d264c))
- Code formatting ([ee8a2fc](https://gitlab.com/openflexure/openflexure-microscope-server/commit/ee8a2fc))
- Code formatting ([7f53ff2](https://gitlab.com/openflexure/openflexure-microscope-server/commit/7f53ff2))
- Code formatting ([76094b2](https://gitlab.com/openflexure/openflexure-microscope-server/commit/76094b2))
- Code formatting and linting ([250fd07](https://gitlab.com/openflexure/openflexure-microscope-server/commit/250fd07))
- Explicit JPEG thumbnail on capture ([09849ce](https://gitlab.com/openflexure/openflexure-microscope-server/commit/09849ce))
- Fixed capture link generator when passed a dict ([353450d](https://gitlab.com/openflexure/openflexure-microscope-server/commit/353450d))
- Fixed gallery overflow ([e3a45b8](https://gitlab.com/openflexure/openflexure-microscope-server/commit/e3a45b8))
- Fixed incorrect import ([89b1f9d](https://gitlab.com/openflexure/openflexure-microscope-server/commit/89b1f9d))
- Fixed node_modules exclusion from Black ([13b4c84](https://gitlab.com/openflexure/openflexure-microscope-server/commit/13b4c84))
- Fixed tab bar scrolling ([279cc03](https://gitlab.com/openflexure/openflexure-microscope-server/commit/279cc03))
- Fixed thumbnail data fallback ([32ec2b4](https://gitlab.com/openflexure/openflexure-microscope-server/commit/32ec2b4))
- Fixed thumbnail generation for video_port captures ([1f12154](https://gitlab.com/openflexure/openflexure-microscope-server/commit/1f12154))
- Fixed View import ([37c5e20](https://gitlab.com/openflexure/openflexure-microscope-server/commit/37c5e20))
- Only save configuration if successfully load new stage type ([b111a4e](https://gitlab.com/openflexure/openflexure-microscope-server/commit/b111a4e))
- Properly set up ESLint ([81ca64e](https://gitlab.com/openflexure/openflexure-microscope-server/commit/81ca64e))
- Rearranged main components ([eff03bf](https://gitlab.com/openflexure/openflexure-microscope-server/commit/eff03bf))
- Removed pointless GPU preview log ([3cfbb40](https://gitlab.com/openflexure/openflexure-microscope-server/commit/3cfbb40))
- Separated move_and_measure locks ([da490fd](https://gitlab.com/openflexure/openflexure-microscope-server/commit/da490fd))
- Upgraded to LabThings 1.1.2 ([654f722](https://gitlab.com/openflexure/openflexure-microscope-server/commit/654f722))
- Use `application/json` for put ([2f08bd3](https://gitlab.com/openflexure/openflexure-microscope-server/commit/2f08bd3))

# [v2.6.5](https://gitlab.com/openflexure/openflexure-microscope-server/compare/v2.6.4...v2.6.5) (2020-10-26)

- 2.6.5 ([9ff0aa3](https://gitlab.com/openflexure/openflexure-microscope-server/commit/9ff0aa3))
- Close #186 ([729e473](https://gitlab.com/openflexure/openflexure-microscope-server/commit/729e473)), closes [#186](https://gitlab.com/openflexure/openflexure-microscope-server/issues/186)

# [v2.6.4](https://gitlab.com/openflexure/openflexure-microscope-server/compare/v2.6.3...v2.6.4) (2020-10-26)

- 2.6.4 ([7a12dfb](https://gitlab.com/openflexure/openflexure-microscope-server/commit/7a12dfb))
- Added a settle time to all stage moves ([58f7686](https://gitlab.com/openflexure/openflexure-microscope-server/commit/58f7686))
- Added a spiral scan option ([ad8fd54](https://gitlab.com/openflexure/openflexure-microscope-server/commit/ad8fd54))
- Changed frame tracker logging level to debug ([9b4031f](https://gitlab.com/openflexure/openflexure-microscope-server/commit/9b4031f))
- Close #148 ([a258b63](https://gitlab.com/openflexure/openflexure-microscope-server/commit/a258b63)), closes [#148](https://gitlab.com/openflexure/openflexure-microscope-server/issues/148)
- Code formatting ([601e51d](https://gitlab.com/openflexure/openflexure-microscope-server/commit/601e51d))
- Fast AF use normal stream ([574f4a6](https://gitlab.com/openflexure/openflexure-microscope-server/commit/574f4a6))
- Reset tracker frames after each mode ([459a8dc](https://gitlab.com/openflexure/openflexure-microscope-server/commit/459a8dc))
