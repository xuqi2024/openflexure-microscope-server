<template>
  <div id="paneNavigate" class="uk-padding-small">
    <div v-if="setPosition">
      <ul uk-accordion="multiple: true">
        <li>
          <a class="uk-accordion-title" href="#">Configure</a>
          <div class="uk-accordion-content">
            <b>STEP SIZE</b>
            <div class="uk-grid-small uk-child-width-1-3" uk-grid>
              <div>
                <label class="uk-form-label" for="form-stacked-text">x</label>
                <div class="uk-form-controls">
                  <input
                    v-model="stepSize.x"
                    class="uk-input uk-form-small"
                    type="number"
                    name="inputStepXy"
                  />
                </div>
                <label class="uk-margin-small-right"
                  ><input
                    v-model="invert.x"
                    class="uk-checkbox"
                    type="checkbox"
                  />
                  Invert x</label
                >
              </div>

              <div>
                <label class="uk-form-label" for="form-stacked-text">y</label>
                <div class="uk-form-controls">
                  <input
                    v-model="stepSize.y"
                    class="uk-input uk-form-small"
                    type="number"
                    name="inputStepY"
                  />
                </div>
                <label class="uk-margin-small-right"
                  ><input
                    v-model="invert.y"
                    class="uk-checkbox"
                    type="checkbox"
                  />
                  Invert y</label
                >
              </div>

              <div>
                <label class="uk-form-label" for="form-stacked-text">z</label>
                <div class="uk-form-controls">
                  <input
                    v-model="stepSize.z"
                    class="uk-input uk-form-small"
                    type="number"
                    name="inputStepZz"
                  />
                </div>
                <label
                  ><input
                    v-model="invert.z"
                    class="uk-checkbox"
                    type="checkbox"
                  />
                  Invert z</label
                >
              </div>
            </div>

            <action-button
              thing="stage"
              action="set_zero_position"
              submit-label="Zero Coordinates"
              :can-terminate="false"
              @finished="updatePosition"
              @error="modalError"
            />
            <action-button
              thing="auto_recentre_stage"
              action="recentre"
              submit-label="Re-centre Stage"
              :can-terminate="true"
              :requires-confirmation="true"
              :modal-progress="true"
              :confirmation-message="
                'The stage will now move, and autofocus will be used to find the centre of motion. This requires a sample to be visible in the microscope. OK to proceed?'
              "
              @finished="updatePosition"
              @error="modalError"
            />
          </div>
        </li>

        <li class="uk-open">
          <a class="uk-accordion-title" href="#">Position</a>
          <div class="uk-accordion-content">
            <form>
              <!-- Text boxes to set and view position -->
              <div class="input-and-buttons-container">
                <input
                  v-for="(_v, key) in setPosition"
                  :key="`setPosition_${key}`"
                  v-model="setPosition[key]"
                  class="uk-form-small numeric-setting-line-input"
                  type="number"
                  @keyup.enter="startMoveTask"
                />
                <a class="button-next-to-input" @click="updatePosition">
                  <span class="material-symbols-outlined">refresh</span>
                </a>
              </div>
              <p>
                <action-button
                  ref="moveButton"
                  thing="stage"
                  action="move_absolute"
                  :submit-data="setPosition"
                  :submit-label="'Move'"
                  :can-terminate="true"
                  :poll-interval="0.05"
                  @taskStarted="moveLock = true"
                  @finished="
                    updatePosition();
                    moveLock = false;
                  "
                  @error="modalError"
                />
              </p>
            </form>
          </div>
        </li>

        <!--Show autofocus if default plugin is enabled-->
        <li class="uk-open">
          <a class="uk-accordion-title" href="#">Autofocus</a>
          <div class="uk-accordion-content">
            <div class="uk-grid-small uk-child-width-expand" uk-grid>
              <div v-show="!isAutofocusing || isAutofocusing == 1">
                <action-button
                  thing="autofocus"
                  action="fast_autofocus"
                  :submit-data="{ dz: 2000 }"
                  :submit-label="'Autofocus'"
                  :button-primary="false"
                  :submit-on-event="'globalFastAutofocusEvent'"
                  @taskStarted="isAutofocusing = 1"
                  @finished="
                    updatePosition();
                    isAutofocusing = 0;
                  "
                  @error="modalError"
                />
              </div>
            </div>
          </div>
        </li>
        <li class="uk-open">
          <a class="uk-accordion-title" href="#">Image Capture</a>
          <div class="uk-accordion-content">
            <div class="uk-margin">
              <action-button
                thing="camera"
                action="capture_jpeg"
                :submit-data="{ resolution: 'main' }"
                :submit-label="'Low Resolution'"
                :submit-on-event="'globalCaptureEvent'"
                @response="handleCaptureResponse"
                @error="modalError"
              />
            </div>

            <div class="uk-margin">
              <action-button
                thing="camera"
                action="capture_jpeg"
                :submit-data="{ resolution: 'full' }"
                submit-label="Full Resolution"
                :submit-on-event="'globalCaptureEvent'"
                @response="handleCaptureResponse"
                @error="modalError"
              />
            </div>
          </div>
        </li>
        <li class="uk-open">
          <a class="uk-accordion-title" href="#">Objective Switcher</a>
          <div class="uk-accordion-content">
            <div class="uk-margin">
              <action-button
                thing="stage"
                action="move_nosepiece"
                :submit-data="{ objective_number: 1 }"
                :submit-label="'Objective #1'"
                @error="modalError"
              />
              <action-button
                thing="stage"
                action="move_nosepiece"
                :submit-data="{ objective_number: 2 }"
                :submit-label="'Objective #2'"
                @error="modalError"
              />
            </div>
          </div>
        </li>
      </ul>
    </div>
    <div v-else class="uk-text-warning">
      <p>Stage positioning is disabled since no stage is connected.</p>
      <p>
        Please check all data and power connections to your motor controller
        board.
      </p>
    </div>
  </div>
</template>

<script>
import axios from "axios";
import ActionButton from "../../labThingsComponents/actionButton.vue";

// Export main app
export default {
  name: "PaneNavigate",

  components: {
    ActionButton
  },

  data: function() {
    return {
      stepXy: 200,
      stepZz: 50,
      stepSize: {
        x: 200,
        y: 200,
        z: 50
      },
      invert: {
        x: false,
        y: false,
        z: false
      },
      setPosition: null,
      isAutofocusing: 0,
      moveLock: false
    };
  },

  computed: {
    baseUri: function() {
      return this.$store.getters.baseUri;
    },
    positionStatusUri: function() {
      return `${this.baseUri}/stage/position`;
    },
    moveInImageCoordinatesUri: function() {
      return this.thingActionUrl(
        "camera_stage_mapping",
        "move_in_image_coordinates"
      );
    },
    things: function() {
      return this.$store.getters["wot/thingDescriptions"];
    }
  },

  watch: {
    stepSize: {
      deep: true,
      handler() {
        this.setLocalStorageObj("navigation_stepSize", this.stepSize);
      }
    },
    invert: {
      deep: true,
      handler() {
        this.setLocalStorageObj("navigation_invert", this.invert);
      }
    }
  },

  async mounted() {
    // Reload saved settings
    this.stepSize =
      this.getLocalStorageObj("navigation_stepSize") || this.stepSize;
    this.invert = this.getLocalStorageObj("navigation_invert") || this.invert;
    let self = this;
    // A global signal listener to perform a move action
    this.$root.$on("globalMoveEvent", self.move);
    // A global signal listener to perform a move action in pixels
    this.$root.$on("globalMoveInImageCoordinatesEvent", (x, y, absolute) => {
      this.moveInImageCoordinatesRequest(x, y, absolute);
    });
    // A global signal listener to perform a move in multiples of a step size
    this.$root.$on("globalMoveStepEvent", (x_steps, y_steps, z_steps) => {
      this.$root.$emit(
        "globalMoveEvent",
        x_steps * this.stepSize.x * (this.invert.x ? -1 : 1),
        y_steps * this.stepSize.y * (this.invert.y ? -1 : 1),
        z_steps * this.stepSize.z * (this.invert.z ? -1 : 1),
        false
      );
    });
    // Update the current position in text boxes
    await this.updatePosition();
  },

  beforeDestroy() {
    // Remove global signal listener to perform a move action
    this.$root.$off("globalMoveEvent");
    this.$root.$off("globalMoveInImageCoordinatesEvent");
    this.$root.$off("globalMoveStepEvent");
  },

  methods: {
    timeout(ms) {
      return new Promise(resolve => setTimeout(resolve, ms));
    },
    async move(x, y, z, absolute) {
      // Move the stage, by updating the controls and starting a move task
      // This is equivalent to clicking the "move" button.
      if (this.moveLock) return; // Discard move requests if we're already moving
      // NB moveLock is just  boolean flag - it's not as safe as a "proper" lock.
      this.moveLock = true; // This will also be set by the task submitter, but
      // setting it here avoids multiple moves being requested simultaneously.
      if (absolute) {
        this.setPosition = { x: x, y: y, z: z };
      } else {
        await this.updatePosition();
        this.setPosition = {
          x: this.setPosition.x + x,
          y: this.setPosition.y + y,
          z: this.setPosition.z + z
        };
      }
      await this.timeout(1); // Wait for Vue to update the position
      await this.startMoveTask();
    },
    async startMoveTask() {
      await this.$refs.moveButton.startTask();
    },
    moveInImageCoordinatesRequest: function(x, y) {
      // If not movement-locked
      if (!this.moveLock) {
        // Lock move requests
        this.moveLock = true;

        if (!this.moveInImageCoordinatesUri) {
          this.modalError(
            "Moving in image coordinates is not supported - you will need to upgrade your microscope's software."
          );
        }

        // Send move request
        axios
          .post(this.moveInImageCoordinatesUri, {
            x: x, // NB the coordinates are numpy/PIL style, meaning X and Y are swapped.
            y: y
          })
          .then(() => {
            this.updatePosition(); // Update the position in text boxes
          })
          .catch(error => {
            this.modalError(error); // Let mixin handle error
          })
          .then(() => {
            this.moveLock = false; // Release the move lock
          });
      }
    },

    async updatePosition() {
      this.setPosition = await this.readThingProperty("stage", "position");
    },

    handleCaptureResponse: async function(response) {
      // Retrieve the captured image and save it
      let imageUri = response.output.href;
      if (!imageUri) {
        this.modalError("No image URI returned from capture task.");
        console.log(`Capture resulted in response ${response}`);
        return;
      }
      // To save the returned data, we make a virtual link and click it
      let imageResponse = await axios.get(imageUri, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([imageResponse.data]));
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", `OFM_${new Date().toISOString()}.jpeg`);
      document.body.appendChild(link);
      link.click();
    }
  }
};
</script>

<style scoped>
.input-and-buttons-container {
  display: flex;
  flex-flow: row wrap;
  justify-content: flex-start;
  align-content: stretch;
  align-items: center;
  width: 100%;
}
.numeric-setting-line-input {
  flex-grow: 1;
  margin-left: 5px;
  margin-right: 5px;
  width: 3em;
}
/* Chrome, Safari, Edge, Opera */
.numeric-setting-line-input::-webkit-outer-spin-button,
.numeric-setting-line-input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
.button-next-to-input {
  flex-grow: 0;
  padding-left: 5px;
  padding-right: 5px;
  vertical-align: middle;
  cursor: pointer;
}
</style>
