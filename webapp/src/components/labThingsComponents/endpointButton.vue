<template>
    <a
      class="uk-button"
      :class="[isDisabled ? 'uk-button-disabled' : '', buttonPrimary ? 'uk-button-primary' : 'uk-button-default']"
      :href="URL"
      download
      > {{ buttonLabel }}</a
    >
</template>

<script>

export default {
  name: "EndpointButton",

  props: {
    buttonPrimary: {
      type: Boolean,
      required: false,
      default: true
    },
    URL: {
      type: String,
      required: true,
    },
    isDisabled: {
      type: Boolean,
      required: false,
      default: false
    },
    destinationName: {
      type: String,
      required: false,
      default: null
    },
    buttonLabel: {
      type: String,
      required: false,
      default: "Download File"
    }
  },
};
</script>

<style lang="less" scoped>
@import "../../assets/less/theme.less";
a.uk-button-disabled {
  pointer-events: none;
}
</style>
