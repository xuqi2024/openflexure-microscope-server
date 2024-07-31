<template>
  <div>
    <!-- eslint-disable-next-line vue/no-v-html -->
    <p v-html="content"></p>
  </div>
</template>

<script>
export default {
  name: "HtmlBlock",

  props: {
    label: {
      type: String,
      required: false,
      default: ""
    },
    name: {
      type: String,
      required: true
    },
    content: {
      type: String,
      required: true
    }
  }
};
</script>

<style scoped></style>
