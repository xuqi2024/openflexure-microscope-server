<template>
  <div v-observe-visibility="visibilityChanged">
    <div id="openseadragon"></div>
  </div>
</template>

<script>
import OpenSeaDragon from "openseadragon";

// Export main app
export default {
  name: "OpenSeadragonViewer",
  components: {},

  props: {
    src: {
      type: String,
      required: true
    }
  },

  data: function() {
    return {
      osdViewer: null
    };
  },

  watch: {
    src: {
      immediate: true,
      handler(newVal) {
        this.loadOpenSeaDragon(newVal);
      }
    }
  },

  async mounted() {
    if (this.src) {
      this.loadOpenSeaDragon(this.src);
    }
  },

  beforeDestroy() {
    // Remove global signal listener to perform a gallery refresh
    this.osdViewer.destroy();
  },

  methods: {
    visibilityChanged(isVisible) {
      if (isVisible) {
        this.loadOpenSeaDragon();
      } else {
        this.osdViewer.destroy();
      }
    },
    async loadOpenSeaDragon() {
      if (this.osdViewer) {
        this.osdViewer.destroy();
      }
      this.osdViewer = OpenSeaDragon({
        id: "openseadragon",
        //prefixUrl: "https://images.openflexure.org/cap_demo/",
        crossOriginPolicy: "Anonymous",
        tileSources: this.src,
        showNavigationControl: false,
        maxZoomPixelRatio: 2,
        gestureSettingsMouse: {
          clickToZoom: false
        }
      });
    },
    openFullscreen() {
      if (this.osdViewer) {
        this.osdViewer.setFullScreen(true);
      }
    }
  }
};
</script>

<style lang="less" scoped>
#openseadragon {
  width: 100%;
  height: 100%;
  background-color: black;
  z-index: 1;
}
#info-panel {
  position: relative;
  top: 10px;
  left: 10px;
  background-color: rgba(255, 255, 255, 0.7);
  padding: 5px;
  border-radius: 1px;
  z-index: 1000;
}
</style>
