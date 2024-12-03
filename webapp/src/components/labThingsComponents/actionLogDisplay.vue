<template>
  <div
    ref="logContainer"
    class="log-container uk-margin-left uk-margin-right uk-margin"
  >
    <div v-if="log">
      <div v-for="(item, index) in log" :key="`log_entry_${index}`">
        {{ item.message }}
      </div>
    </div>
    <div v-if="taskStatus == 'error'" class="uk-alert uk-alert-danger">
      The task failed due to an error. There may be more information in the log.
    </div>
    <div v-if="taskStatus == 'cancelled'" class="uk-alert uk-alert-warning">
      The task was cancelled.
    </div>
    <div v-if="taskStatus == 'completed'" class="uk-alert uk-alert-success">
      The task completed successfully.
    </div>
  </div>
</template>

<script>
export default {
  name: "ActionLogDisplay",

  props: {
    taskStatus: {
      type: String,
      required: true
    },
    log: {
      type: Array,
      required: true
    }
  },

  watch: {
    log: function() {
      this.scrollToBottom();
    },
    taskStatus: function() {
      this.scrollToBottom();
    }
  },

  methods: {
    scrollToBottom() {
      this.$nextTick(function() {
        let viewer = this.$refs.logContainer;
        viewer.scrollTop = viewer.scrollHeight;
      });
    }
  }
};
</script>

<style scoped>
.log-container {
  position: relative;
  overflow-y: auto;
  overflow-x: auto;
  background-color: white;
  color: black;
  padding: 0.5em;
  border: 1px solid black;
}
</style>
