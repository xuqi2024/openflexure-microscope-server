<template>
  <div
    id="stream-display"
    ref="streamDisplay"
    v-observe-visibility="visibilityChanged"
    class="stream-display uk-width-1-1 uk-height-1-1 scrollTarget"
  >
    <img
      v-if="isVisible"
      ref="click-frame"
      class="uk-align-center uk-margin-remove-bottom"
      :hidden="!streamEnabled"
      :src="streamImgUri"
      alt="Stream"
      @dblclick="clickMonitor"
    />

    <div v-if="!streamEnabled" class="uk-height-1-1">
      <div v-if="$store.state.waiting" class="uk-position-center">
        <div uk-spinner="ratio: 4.5" />
      </div>

      <div
        v-else-if="$store.state.disableStream"
        class="uk-position-center position-relative text-center"
      >
        Stream preview disabled
      </div>

      <div v-else class="uk-position-center position-relative text-center">
        No active connection
      </div>
    </div>
  </div>
</template>

<script>
import axios from "axios";

// Export main app
export default {
  name: "StreamDisplay",

  data: function () {
    return {
      isVisible: false,
      displaySize: [0, 0],
      displayPosition: [0, 0],
      resizeTimeoutId: setTimeout(this.doneResizing, 500),
    };
  },

  computed: {
    streamEnabled: function () {
      return this.$store.getters.ready && !this.$store.state.disableStream;
    },
    thisStreamOpen: function () {
      // Only a single MJPEG connection should be open at a time
      return !(this.displaySize[0] == 0) && !(this.displaySize[1] == 0);
    },
    streamImgUri: function () {
      return `${this.$store.getters.baseUri}/api/v2/streams/mjpeg`;
    },
    startPreviewUri: function () {
      return `${this.$store.getters.baseUri}/api/v2/actions/camera/preview/start`;
    },
    stopPreviewUri: function () {
      return `${this.$store.getters.baseUri}/api/v2/actions/camera/preview/stop`;
    },
    settingsUri: function () {
      return `${this.$store.getters.baseUri}/api/v2/instrument/settings`;
    },
  },

  mounted() {
    console.log(`${this._uid} mounted`);
    // A global signal listener to change the GPU preview state
    this.$root.$on("globalTogglePreview", (state) => {
      this.previewRequest(state);
    });
    this.$root.$on("globalSafeTogglePreview", (state) => {
      this.safePreviewRequest(state);
    });
    // A global signal listener to flash the stream element
    this.$root.$on("globalFlashStream", () => {
      this.flashStream();
    });

    // Mutation observer
    this.sizeObserver = new ResizeObserver(() => {
      this.handleResize(); // For any element attached to the observer, run handleResize() on change
    });
    // Fetch streamDisplay component by ref
    const streamDisplayElement = this.$refs.streamDisplay.parentNode;
    // Attach streamDisplay to the size observer
    this.sizeObserver.observe(streamDisplayElement);
  },

  created: function () {
    console.log(`${this._uid} created`);
    // Send a request to start/stop GPU preview based on global setting
    this.safePreviewRequest(this.$store.state.autoGpuPreview);
  },

  beforeDestroy: function () {
    console.log(`${this._uid} being destroyed`);
    // Remove global signal listener to change the GPU preview state
    this.$root.$off("globalTogglePreview");
    // Remove global signal listener to flash the stream element
    this.$root.$off("globalFlashStream");
    // Disconnect the size observer
    this.sizeObserver.disconnect();
    // Remove from the array of active streams
    this.$store.commit("removeStream", this._uid);
  },

  methods: {
    visibilityChanged(isVisible) {
      this.isVisible = isVisible;
    },
    flashStream: function () {
      // Run an animation that flashes the stream (for capture feedback)
      const element = this.$refs.streamDisplay;
      element.classList.remove("uk-animation-fade");
      element.offsetHeight; /* trigger reflow */
      element.classList.add("uk-animation-fade");
      setTimeout(function () {
        element.classList.remove("uk-animation-fade");
      }, 800);
    },

    clickMonitor: function (event) {
      // Calculate steps from event coordinates
      const xCoordinate = event.offsetX;
      const yCoordinate = event.offsetY;

      // Simply scaling by naturalHeight/offsetHeight may give the wrong answer!
      // because we use content-fit: contain in the stylesheet, the img element
      // may be larger than the picture.  So, we must determine whether the
      // width or height is setting the scaling factor, and use a uniform scale
      // factor.
      const scale = Math.max(
        event.target.naturalWidth / event.target.offsetWidth,
        event.target.naturalHeight / event.target.offsetHeight
      );

      const xRelative = (0.5 * event.target.offsetWidth - xCoordinate) * scale;
      const yRelative = (0.5 * event.target.offsetHeight - yCoordinate) * scale;

      // Emit a signal to move, acted on by panelNavigate.vue
      this.$root.$emit(
        "globalMoveInImageCoordinatesEvent",
        -xRelative,
        -yRelative
      );
    },

    handleResize: function () {
      // Only fires resize event after no resize in 500ms (prevents resize event spam)
      clearTimeout(this.resizeTimeoutId);
      this.resizeTimeoutId = setTimeout(this.handleDoneResize, 250);
    },

    handleDoneResize: function () {
      // Recalculate size
      console.log(`Recalculating frame size for ${this._uid}`);
      this.recalculateSize();
      // Handle closed stream
      if (this.displaySize[0] == 0 && this.displaySize[1] == 0) {
        console.log(`${this._uid} is zero`);
        // If this stream was previously active
        if (this.$store.state.activeStreams[this._uid] == true) {
          console.log(`${this._uid} was active`);
          console.log(`STREAM ${this._uid} CLOSED`);
          this.$store.commit("removeStream", this._uid);
          // If all streams are closed, request the GPU preview close
          const a = Object.values(this.$store.state.activeStreams);
          const allClosed = a.every((v) => v === false);
          if (allClosed) {
            this.safePreviewRequest(false);
          }
        }
        // If resized to anything other than zero
      } else {
        console.log(`STREAM ${this._uid} OPEN`);
        this.$store.commit("addStream", this._uid);
        if (this.$store.state.autoGpuPreview == true) {
          // Start the preview immediately
          this.safePreviewRequest(true);
          // Send another start preview request after a timeout
          /*
          The internal logic of this component means that a stop GPU preview
          request will only ever be sent if ALL stream components are invisible.
          However, when switching tabs, sometimes the previous component will
          react to becoming invisible before the new tab has become visible.
          This results in a stop-preview request being sent JUST before the new
          start preview request is sent. In an ideal network, this is fine, however
          due to network jitter, these requests will occasionally be recieved out
          of order, causing the preview to start in the new location, and then 
          quickly stop again.
          Preventing this properly will involve some clever server-side logic
          probably, however as a pit-stop solution, we always send another
          start-preview request after 1 second. This means that either:
          1. The initial requests happened in order, in which case this follow-up
          request does nothing, or
          2. The requests leapfrog eachother, stopping the preview, in which case
          the follow-up request restarts the preview in the correct location.
          */
          setTimeout(() => this.safePreviewRequest(true), 250);
        }
      }
    },

    recalculateSize: function () {
      // Calculate stream size
      const element = this.$refs.streamDisplay.parentNode;
      const bound = element.getBoundingClientRect();

      const elementSize = [bound.width, bound.height];

      const elementPositionOnWindow = [bound.left, bound.top];
      const windowPositionOnDisplay = [window.screenX, window.screenY];
      const windowChromeHeight = window.outerHeight - window.innerHeight;
      const elementPositionOnDisplay = [
        Math.max(0, windowPositionOnDisplay[0] + elementPositionOnWindow[0]),
        Math.max(
          0,
          windowPositionOnDisplay[1] +
            elementPositionOnWindow[1] +
            windowChromeHeight
        ),
      ];

      this.displaySize = elementSize;
      this.displayPosition = elementPositionOnDisplay;
    },

    safePreviewRequest: function (state) {
      // previewRequest, but only stopping preview if all streams are invisible
      // and only starting preview if any stream is visible
      const a = Object.values(this.$store.state.activeStreams);
      const allClosed = a.every((v) => v === false);
      // If all streams are closed, don't start GPU preview
      if (state === true && allClosed) {
        return false;
      }
      // If not all streams are closed, don't stop GPU preview
      if (state === false && !allClosed) {
        return false;
      }
      return this.previewRequest(state);
    },

    previewRequest: function (state) {
      // If requesting starting the stream, but this component is inactive, skip
      if (
        this.$store.getters.ready == true &&
        this.$store.state.autoGpuPreview == true
      ) {
        let requestUri = null;
        // Create URI
        if (state == true) {
          requestUri = this.startPreviewUri;
        } else {
          requestUri = this.stopPreviewUri;
        }

        // Generate payload if tracking window position
        let payload = {};
        if (this.$store.state.trackWindow == true && state == true) {
          // Recalculate frame dimensions and position
          this.recalculateSize();
          // Copy data into payload array
          payload = {
            window: [
              this.displayPosition[0],
              this.displayPosition[1],
              this.displaySize[0],
              this.displaySize[1],
            ],
          };
        }

        // Send preview request
        console.log(`${this._uid} toggled preview to ${state}`);
        axios.post(requestUri, payload).catch((error) => {
          this.modalError(error); // Let mixin handle error
        });
      }
    },
  },
};
</script>

<style scoped lang="less">
.stream-display img {
  height: 100%;
  text-align: center;
  object-fit: contain;
}

.stream-display {
  width: 100%;
  height: 100%;
}

.position-relative {
  position: relative !important;
}

.text-center {
  text-align: center;
}
</style>
