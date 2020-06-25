<template>
  <div
    id="stream-display"
    ref="streamDisplay"
    class="stream-display uk-width-1-1 uk-height-1-1 scrollTarget"
  >
    <img
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

  data: function() {
    return {};
  },

  computed: {
    streamImgUri: function() {
      return `${this.$store.getters.baseUri}/api/v2/streams/mjpeg`;
    }
  },
  methods: {}
};
</script>

<style scoped lang="less">
.stream-display img {
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
