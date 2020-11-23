<template>
  <div
    v-observe-visibility="visibilityChanged"
    class="uk-margin-remove uk-padding-remove"
  >
    <div v-if="taskStarted" ref="isPollingElement">
      <div class="progress uk-margin-small">
        <div
          v-if="progress"
          class="determinate"
          :style="barWidthFromProgress"
        ></div>
        <div v-else class="indeterminate"></div>
      </div>

      <button
        v-if="canTerminate && taskRunning"
        type="button"
        class="uk-button uk-button-danger uk-margin-remove uk-float-right uk-width-1-1"
        @click="terminateTask()"
      >
        Cancel
      </button>
    </div>

    <div>
      <button
        type="button"
        :hidden="taskStarted"
        class="uk-button uk-margin-remove uk-width-1-1"
        :class="[buttonPrimary ? 'uk-button-primary' : 'uk-button-default']"
        @click="bootstrapTask()"
      >
        {{ submitLabel }}
      </button>
    </div>
  </div>
</template>

<script>
import axios from "axios";

export default {
  name: "TaskSubmitter",

  props: {
    submitUrl: {
      type: String,
      required: true
    },
    submitData: {
      type: [Object, Array],
      required: false,
      default: () => ({})
    },
    pollInterval: {
      type: Number,
      required: false,
      default: 1
    },
    submitLabel: {
      type: String,
      required: false,
      default: "Submit"
    },
    canTerminate: {
      type: Boolean,
      required: false,
      default: true
    },
    requiresConfirmation: {
      type: Boolean,
      required: false,
      default: false
    },
    confirmationMessage: {
      type: String,
      required: false,
      default: "Start task?"
    },
    buttonPrimary: {
      type: Boolean,
      required: false,
      default: true
    },
    submitOnEvent: {
      type: String,
      required: false,
      default: null
    }
  },

  emits: [
    "task-started",
    "task-running",
    "submit",
    "response",
    "finished",
    "error"
  ],

  data: function() {
    return {
      taskId: null,
      taskUrl: null,
      progress: null,
      taskStarted: false,
      taskRunning: false
    };
  },

  computed: {
    barWidthFromProgress: function() {
      var progress = this.progress <= 100 ? this.progress : 100;
      var styleString = `width: ${progress}%`;
      return styleString;
    }
  },

  created() {},

  mounted() {
    // Check for already running tasks
    if (this.taskStarted != true) {
      this.checkExistingTasks();
    }
    // A global signal listener to perform the action
    if (this.submitOnEvent) {
      this.$emitter.on(this.submitOnEvent, () => {
        this.bootstrapTask();
      });
    }
  },

  beforeUnmount() {
    if (this.submitOnEvent) {
      this.$root.$off(this.submitOnEvent);
    }
  },

  methods: {
    visibilityChanged(isVisible) {
      if (isVisible && this.taskStarted != true) {
        this.checkExistingTasks();
      }
    },

    checkExistingTasks: function() {
      axios.get(this.submitUrl).then(response => {
        for (const task of response.data) {
          if (task.status == "pending" || task.status == "running") {
            this.taskStarted = true;
            this.$emit("task-started", this.taskId);
            this.startPolling(task.id, task.links.self.href);
          }
        }
      });
    },

    bootstrapTask: function() {
      // Starts the process of creating a new Actiont ask
      if (this.requiresConfirmation) {
        this.modalConfirm(this.confirmationMessage).then(
          () => {
            this.startTask();
          },
          () => {}
        );
      } else {
        this.startTask();
      }
    },

    startTask: function() {
      // Starts a new Action task

      this.$emit("submit", this.submitData);
      // Send a request to start a task

      this.taskStarted = true;
      this.$emit("task-started", this.taskId);
      axios
        .post(this.submitUrl, this.submitData)
        // Get the returned Task ID
        .then(response => {
          // Start the store polling TaskId for success
          this.startPolling(response.data.id, response.data.href);
        });
    },

    startPolling: function(taskId, taskUrl) {
      if (this.taskRunning != true) {
        // Starts polling an existing Action task
        this.taskId = taskId;
        this.taskUrl = taskUrl;
        // Start the store polling TaskId for success
        this.taskRunning = true;
        this.$emit("task-running", this.taskId);
        this.pollTask(this.taskId, this.pollInterval)
          .then(response => {
            // Do something with the final response

            this.$emit("response", response);
            this.$emit("finished");
          })
          .catch(error => {
            if (!error) {
              error = Error("Unknown error");
            }

            this.$emit("error", error);
            this.$emit("finished");
          })
          .finally(() => {
            // Reset taskRunning and taskId
            this.taskRunning = false;
            this.taskStarted = false;
            this.taskId = null;
            // Update the form data if we're self-updating
            if (this.selfUpdate) {
              this.getFormData();
            }
          });
      }
    },

    pollTask: function(taskId, interval) {
      interval = interval * 1000 || 500;

      var checkCondition = (resolve, reject) => {
        // If the condition is met, we're done!
        axios.get(this.taskUrl).then(response => {
          var result = response.data.status;
          // If the task ends with success
          if (result == "completed") {
            resolve(response.data);
          }
          // If task ends with an error
          else if (result == "error") {
            // Pass the error string back with reject

            reject(new Error(response.data.output));
          }
          // If task ends with termination
          else if (result == "cancelled") {
            // Pass a generic termination error back with reject

            reject(new Error("Task cancelled"));
          } else {
            // Since the task is still running, we can update the progress bar
            this.progress = response.data.progress;
            // Check again after timeout
            setTimeout(checkCondition, interval, resolve, reject);
          }
        });
      };

      return new Promise(checkCondition);
    },

    pollProgress: function() {
      axios.get(this.taskUrl).then(response => {
        this.progress = response.data.progress;
      });
    },

    terminateTask: function() {
      axios.delete(this.taskUrl);
    }
  }
};
</script>

<style lang="less" scoped>
@import "../../assets/less/theme.less";

.progress {
  position: relative;
  height: 5px;
  display: block;
  width: 100%;
  background-color: rgba(180, 180, 180, 0.15);
  border-radius: 2px;
  background-clip: padding-box;
  margin: 0.5rem 0 1rem 0;
  overflow: hidden;
}

.progress .determinate {
  position: absolute;
  background-color: inherit;
  top: 0;
  bottom: 0;
  transition: width 0.3s linear;
}

.progress .indeterminate,
.progress .determinate {
  background-color: @global-primary-background;
}

.hook-inverse() {
  .progress .indeterminate,
  .progress .determinate {
    background-color: @inverse-primary-muted-color;
  }
}

.progress .indeterminate:before {
  content: "";
  position: absolute;
  background-color: inherit;
  top: 0;
  left: 0;
  bottom: 0;
  will-change: left, right;
  -webkit-animation: indeterminate 2.1s cubic-bezier(0.65, 0.815, 0.735, 0.395)
    infinite;
  animation: indeterminate 2.1s cubic-bezier(0.65, 0.815, 0.735, 0.395) infinite;
}

.progress .indeterminate:after {
  content: "";
  position: absolute;
  background-color: inherit;
  top: 0;
  left: 0;
  bottom: 0;
  will-change: left, right;
  -webkit-animation: indeterminate-short 2.1s cubic-bezier(0.165, 0.84, 0.44, 1)
    infinite;
  animation: indeterminate-short 2.1s cubic-bezier(0.165, 0.84, 0.44, 1)
    infinite;
  -webkit-animation-delay: 1.15s;
  animation-delay: 1.15s;
}

@-webkit-keyframes indeterminate {
  0% {
    left: -35%;
    right: 100%;
  }
  60% {
    left: 100%;
    right: -90%;
  }
  100% {
    left: 100%;
    right: -90%;
  }
}
@keyframes indeterminate {
  0% {
    left: -35%;
    right: 100%;
  }
  60% {
    left: 100%;
    right: -90%;
  }
  100% {
    left: 100%;
    right: -90%;
  }
}
@-webkit-keyframes indeterminate-short {
  0% {
    left: -200%;
    right: 100%;
  }
  60% {
    left: 107%;
    right: -8%;
  }
  100% {
    left: 107%;
    right: -8%;
  }
}
@keyframes indeterminate-short {
  0% {
    left: -200%;
    right: 100%;
  }
  60% {
    left: 107%;
    right: -8%;
  }
  100% {
    left: 107%;
    right: -8%;
  }
}
</style>
