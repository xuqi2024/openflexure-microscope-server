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
      :src="streamImgUri"
      alt="Stream"
    />
  </div>
</template>

<script>
// Export main app
export default {
  name: "MiniStreamDisplay",

  data: function () {
    return {
      isVisible: false,
    };
  },

  computed: {
    streamImgUri: function () {
      return `${this.$store.getters.baseUri}/api/v2/streams/mjpeg`;
    },
  },
  methods: {
    visibilityChanged(isVisible) {
      this.isVisible = isVisible;
    },
  },
};
</script>

<style scoped lang="less">
.stream-display img {
  text-align: center;
  object-fit: contain;
  border: 1px solid #555;
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
