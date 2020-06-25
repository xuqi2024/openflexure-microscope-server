<template>
  <div>
    <div
      class="progress uk-margin-top uk-margin-horizontal-remove uk-padding-remove"
    >
      <div
        v-if="progress"
        class="determinate"
        :style="barWidthFromProgress"
      ></div>
      <div v-else class="indeterminate"></div>
    </div>

    <button
      type="button"
      class="uk-button uk-button-danger uk-form-small uk-float-right uk-width-1-1"
      @click="terminateTask()"
    >
      Terminate
    </button>
  </div>
</template>

<script>
import axios from "axios";

export default {
  name: "TaskProgress",

  props: {
    taskId: {
      type: String,
      required: true
    },
    pollInterval: {
      type: Number,
      required: false,
      default: 500
    }
  },

  data: function() {
    return {
      polling: null,
      progress: null
    };
  },

  computed: {
    barWidthFromProgress: function() {
      var progress = this.progress <= 100 ? this.progress : 100;
      var styleString = `width: ${progress}%`;
      return styleString;
    }
  },

  created() {
    this.polling = setInterval(() => {
      this.pollProgress();
    }, this.pollInterval);
  },

  beforeDestroy() {
    clearInterval(this.polling);
  },

  methods: {
    pollProgress: function() {
      console.log("Starting progress polling");
      axios
        .get(`${this.$store.getters.uriV2}/tasks/${this.taskId}`)
        .then(response => {
          console.log("PROGRESS RESPONSE: ", response.data.progress);
          this.progress = response.data.progress;
        });
    },

    terminateTask: function() {
      axios
        .delete(`${this.$store.getters.uriV2}/tasks/${this.taskId}`)
        .then(response => {
          console.log("TERMINATION RESPONSE: ", response.data);
        });
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
