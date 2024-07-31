<template>
  <div
    v-observe-visibility="visibilityChanged"
    class="uk-margin-remove uk-padding-remove"
  >
    <div v-if="taskStarted" ref="isPollingElement">
      <action-progress-bar :progress="progress" :task-status="taskStatus" />
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

    <div
      id="modal-center"
      ref="statusModal"
      class=""
      uk-modal="bg-close: false; esc-close: false; stack: true;"
    >
      <div
        id="status-modal"
        class="uk-modal-dialog uk-modal-body uk-margin-auto-vertical"
      >
        <h2>{{ submitLabel }}</h2>
        <action-log-display :log="log" :task-status="taskStatus" />
        <div id="progress-and-cancel-row">
          <div class="stretchy">
            <action-progress-bar
              :progress="progress"
              :task-status="taskStatus"
            />
          </div>

          <button
            v-if="canTerminate && taskRunning"
            type="button"
            class="uk-button uk-button-danger not-stretchy"
            @click="terminateTask()"
          >
            Cancel
          </button>
          <button
            v-if="!taskStarted"
            type="button"
            class="uk-button not-stretchy"
            @click="hideModal"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from "axios";
import UIkit from "uikit";
import ActionProgressBar from "./actionProgressBar.vue";
import ActionLogDisplay from "./actionLogDisplay.vue";

export default {
  name: "ActionButton",
  components: { ActionProgressBar, ActionLogDisplay },

  props: {
    action: {
      type: String,
      required: true
    },
    thing: {
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
    },
    modalProgress: {
      type: Boolean,
      required: false,
      default: false
    }
  },

  data: function() {
    return {
      taskUrl: null,
      progress: null,
      taskStarted: false,
      taskRunning: false,
      log: [],
      taskStatus: ""
    };
  },

  computed: {
    submitUrl() {
      return this.thingActionUrl(this.thing, this.action);
    }
  },

  watch: {
    progress(newval) {
      this.$emit("update:progress", newval);
    },
    taskStarted(newval) {
      this.$emit("update:taskStarted", newval);
    },
    taskRunning(newval) {
      this.$emit("update:taskRunning", newval);
    },
    log(newval) {
      this.$emit("update:log", newval);
    },
    taskStatus(newval) {
      this.$emit("update:taskStatus", newval);
    }
  },

  mounted() {
    // Check for already running tasks
    if (this.taskStarted != true) {
      this.checkExistingTasks();
    }
    // A global signal listener to perform the action
    if (this.submitOnEvent) {
      this.$root.$on(this.submitOnEvent, () => {
        this.bootstrapTask();
      });
    }
  },

  beforeDestroy() {
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
            this.$emit("taskStarted");
            this.startPolling(
              task.id,
              task.links.find(t => t.rel == "self").href
            );
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

    async startTask() {
      // Starts a new Action task

      this.$emit("submit", this.submitData);
      // Send a request to start a task

      this.taskStarted = true;
      this.$emit("taskStarted");
      try {
        let response = await axios.post(this.submitUrl, this.submitData);
        if (this.modalProgress) {
          UIkit.modal(this.$refs.statusModal).show();
        }
        // Start the store polling TaskId for success
        response = await this.startPolling(
          response.data.id,
          response.data.href
        );
        if (response.status == "completed") {
          this.$emit("response", response);
          this.$emit("completed", response.output);
        } else if (response.status == "cancelled") {
          this.$emit("cancelled", response);
          this.modalNotify(`The action '${this.submitLabel}' was cancelled.`);
        }
      } catch (error) {
        this.$emit("error", error | Error("Unknown error"));
      } finally {
        // Reset taskRunning and taskId
        this.taskRunning = false;
        this.taskStarted = false;
        this.$emit("finished");
        // Update the form data if we're self-updating
        if (this.selfUpdate) {
          this.getFormData();
        }
      }
    },

    startPolling: function(taskId, taskUrl) {
      if (this.taskRunning != true) {
        // Starts polling an existing Action task
        this.taskUrl = taskUrl;
        // Start the store polling TaskId for success
        this.taskRunning = true;
        this.$emit("taskRunning", taskId);
        return this.pollTask(taskId, this.pollInterval);
      }
    },

    pollTask: function(taskId, interval) {
      interval = interval * 1000 || 500;

      var checkCondition = (resolve, reject) => {
        // If the condition is met, we're done!
        axios
          .get(this.taskUrl, { baseURL: this.$store.getters.baseUri })
          .then(response => {
            var result = response.data.status;
            this.taskStatus = result;
            if ((result == "running") | (result == "pending")) {
              // If the task is still running, we update progress/log,
              // and schedule another poll
              this.progress = response.data.progress;
              this.log = response.data.log;
              // Check again after timeout
              setTimeout(checkCondition, interval, resolve, reject);
            }
            // If task ends with an error
            else if (result == "error") {
              // Pass the error string back with reject
              if (!this.progress) this.progress = 1;
              reject(new Error(response.data.output));
            }
            // If task ends without reporting an error
            // (NB this includes cancellation)
            else {
              resolve(response.data);
            }
          });
      };

      return new Promise(checkCondition);
    },

    hideModal() {
      UIkit.modal(this.$refs.statusModal).hide();
    },

    terminateTask: function() {
      axios.delete(this.taskUrl, { baseURL: this.$store.getters.baseUri });
    }
  }
};
</script>

<style lang="less" scoped>
@import "../../assets/less/theme.less";

#progress-and-cancel-row {
  display: flex;
  flex-flow: row wrap;
  justify-content: flex-start;
  align-content: stretch;
  align-items: center;
  width: 100%;
}

#progress-and-cancel-row .stretchy {
  flex-grow: 1;
  margin-left: 5px;
  margin-right: 5px;
}
#progress-and-cancel-row .not-stretchy {
  flex-grow: 0;
  margin-left: 5px;
  margin-right: 5px;
}

#status-modal .log-container {
  height: 10em;
}
</style>
