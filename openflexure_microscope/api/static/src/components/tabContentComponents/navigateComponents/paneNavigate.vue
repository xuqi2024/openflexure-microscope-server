<template>
  <div id="paneNavigate" class="uk-padding-small">
    <div v-if="setPosition">
      <ul uk-accordion="multiple: true">
        <li>
          <a class="uk-accordion-title" href="#">Configure</a>
          <div class="uk-accordion-content">
            <div class="uk-child-width-1-2" uk-grid>
              <div>
                <label class="uk-form-label" for="form-stacked-text"
                  >x-y step size</label
                >
                <div class="uk-form-controls">
                  <input
                    v-model="stepXy"
                    class="uk-input uk-form-width-medium uk-form-small"
                    type="number"
                    name="inputStepXy"
                  />
                </div>
              </div>

              <div>
                <label class="uk-form-label" for="form-stacked-text"
                  >z step size</label
                >
                <div class="uk-form-controls">
                  <input
                    v-model="stepZz"
                    class="uk-input uk-form-width-medium uk-form-small"
                    type="number"
                    name="inputStepZz"
                  />
                </div>
              </div>
            </div>

            <button
              class="uk-button uk-button-default uk-margin uk-width-1-1"
              @click="zeroRequest()"
            >
              Zero coordinates
            </button>
          </div>
        </li>

        <li class="uk-open">
          <a class="uk-accordion-title" href="#">Move-to</a>
          <div class="uk-accordion-content">
            <form @submit.prevent="handleSubmit">
              <!-- Text boxes to set and view position -->

              <div class="uk-grid-small uk-child-width-1-3" uk-grid>
                <div>
                  <label class="uk-form-label" for="form-stacked-text">x</label>
                  <div class="uk-form-controls">
                    <input
                      v-model="setPosition.x"
                      class="uk-input uk-form-small"
                      type="number"
                      name="inputPositionX"
                    />
                  </div>
                </div>

                <div>
                  <label class="uk-form-label" for="form-stacked-text">y</label>
                  <div class="uk-form-controls">
                    <input
                      v-model="setPosition.y"
                      class="uk-input uk-form-small"
                      type="number"
                      name="inputPositionY"
                    />
                  </div>
                </div>

                <div>
                  <label class="uk-form-label" for="form-stacked-text">z</label>
                  <div class="uk-form-controls">
                    <input
                      v-model="setPosition.z"
                      class="uk-input uk-form-small"
                      type="number"
                      name="inputPositionZx"
                    />
                  </div>
                </div>
              </div>

              <p>
                <button
                  type="submit"
                  class="uk-button uk-button-default uk-float-right uk-width-1-1"
                >
                  Move
                </button>
              </p>
            </form>
          </div>
        </li>

        <!--Show autofocus if default plugin is enabled-->
        <li v-show="fastAutofocusUri || normalAutofocusUri" class="uk-open">
          <a class="uk-accordion-title" href="#">Autofocus</a>
          <div class="uk-accordion-content">
            <div class="uk-grid-small uk-child-width-expand" uk-grid>
              <div v-show="!isAutofocusing || isAutofocusing == 1">
                <taskSubmitter
                  v-if="fastAutofocusUri"
                  :submit-url="fastAutofocusUri"
                  :submit-data="{ dz: 2000 }"
                  :submit-label="'Fast'"
                  :button-primary="false"
                  :submit-on-event="'globalFastAutofocusEvent'"
                  @taskStarted="isAutofocusing = 1"
                  @finished="isAutofocusing = 0"
                ></taskSubmitter>
              </div>

              <div v-show="!isAutofocusing || isAutofocusing == 2">
                <taskSubmitter
                  v-if="normalAutofocusUri"
                  :submit-url="normalAutofocusUri"
                  :submit-data="{ dz: [-90, -60, -30, 0, 30, 60, 90] }"
                  :submit-label="'Medium'"
                  :button-primary="false"
                  @taskStarted="isAutofocusing = 2"
                  @finished="isAutofocusing = 0"
                ></taskSubmitter>
              </div>

              <div v-show="!isAutofocusing || isAutofocusing == 3">
                <taskSubmitter
                  v-if="normalAutofocusUri"
                  :submit-url="normalAutofocusUri"
                  :submit-data="{ dz: [-30, -20, -10, 0, 10, 20, 30] }"
                  :submit-label="'Fine'"
                  :button-primary="false"
                  @taskStarted="isAutofocusing = 3"
                  @finished="isAutofocusing = 0"
                ></taskSubmitter>
              </div>
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
import taskSubmitter from "../../genericComponents/taskSubmitter";

// Export main app
export default {
  name: "PaneNavigate",

  components: {
    taskSubmitter
  },

  data: function() {
    return {
      stepXy: 200,
      stepZz: 50,
      setPosition: null,
      isAutofocusing: 0,
      moveLock: false,
      fastAutofocusUri: null,
      normalAutofocusUri: null,
      moveInImageCoordinatesUri: null
    };
  },

  computed: {
    moveActionUri: function() {
      return `${this.$store.getters.baseUri}/api/v2/actions/stage/move`;
    },
    zeroActionUri: function() {
      return `${this.$store.getters.baseUri}/api/v2/actions/stage/zero`;
    },
    positionStatusUri: function() {
      return `${this.$store.getters.baseUri}/api/v2/instrument/state/stage/position`;
    },
    pluginsUri: function() {
      return `${this.$store.getters.baseUri}/api/v2/extensions`;
    }
  },

  mounted() {
    // A global signal listener to perform a move action
    this.$emitter.on("globalMoveEvent", (x, y, z, absolute) => {
      this.moveRequest(x, y, z, absolute);
    });
    // A global signal listener to perform a move action in pixels
    this.$emitter.on("globalMoveInImageCoordinatesEvent", (x, y, absolute) => {
      this.moveInImageCoordinatesRequest(x, y, absolute);
    });
    // A global signal listener to perform a move in multiples of a step size
    this.$emitter.on("globalMoveStepEvent", (x_steps, y_steps, z_steps) => {
      this.moveRequest(
        x_steps * this.stepXy,
        y_steps * this.stepXy,
        z_steps * this.stepZz,
        false
      );
    });
    // Update the current position in text boxes
    this.updatePosition();
    // Look for autofocus plugin
    this.updateAutofocusUri();
    this.updateMoveInImageCoordinatesUri();
  },

  beforeUnmount() {
    // Remove global signal listener to perform a move action
    this.$root.$off("globalMoveEvent");
    this.$root.$off("globalMoveInImageCoordinatesEvent");
    this.$root.$off("globalMoveStepEvent");
  },

  methods: {
    handleSubmit: function() {
      this.moveRequest(
        this.setPosition.x,
        this.setPosition.y,
        this.setPosition.z,
        true
      );
    },

    moveRequest: function(x, y, z, absolute) {
      // If not movement-locked
      if (!this.moveLock) {
        // Lock move requests
        this.moveLock = true;

        // Send move request
        axios
          .post(this.moveActionUri, {
            x: x,
            y: y,
            z: z,
            absolute: absolute
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
            x: y, // NB the coordinates are numpy/PIL style, meaning X and Y are swapped.
            y: x
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

    zeroRequest: function() {
      // Send move request
      axios
        .post(this.zeroActionUri)
        .then(() => {
          this.updatePosition(); // Update the position in text boxes
        })
        .catch(error => {
          this.modalError(error); // Let mixin handle error
        });
    },

    updatePosition: function() {
      axios
        .get(this.positionStatusUri)
        .then(response => {
          this.setPosition = response.data;
        })
        .catch(error => {
          this.modalError(error); // Let mixin handle error
        });
    },

    updateAutofocusUri: function() {
      axios
        .get(this.pluginsUri) // Get a list of plugins
        .then(response => {
          var plugins = response.data;
          var foundExtension = plugins.find(
            e => e.title === "org.openflexure.autofocus"
          );
          // if ScanPlugin is enabled
          if (foundExtension) {
            // Get plugin action link
            this.fastAutofocusUri = foundExtension.links.fast_autofocus.href;
            this.normalAutofocusUri = foundExtension.links.autofocus.href;
          }
        })
        .catch(error => {
          this.modalError(error); // Let mixin handle error
        });
    },

    updateMoveInImageCoordinatesUri: function() {
      axios
        .get(this.pluginsUri) // Get a list of plugins
        .then(response => {
          var plugins = response.data;
          var foundExtension = plugins.find(
            e => e.title === "org.openflexure.camera_stage_mapping"
          );
          if (foundExtension) {
            // Get plugin action link
            this.moveInImageCoordinatesUri =
              foundExtension.links.move_in_image_coordinates.href;
          }
        })
        .catch(error => {
          this.modalError(error); // Let mixin handle error
        });
    }
  }
};
</script>
