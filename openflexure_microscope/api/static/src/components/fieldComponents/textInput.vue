<template>
  <div>
    <label v-if="label" class="uk-form-label">{{ label }}</label>

    <input
      class="uk-input uk-form-small"
      type="text"
      :name="name"
      :value="value"
      :placeholder="placeholder"
      v-bind="$attrs"
      @input="$emit('input', $event.target.value)"
    />
  </div>
</template>

<script>
export default {
  name: "TextInput",

  props: {
    placeholder: {
      type: String,
      required: false,
      default: null
    },
    label: {
      type: String,
      required: false,
      default: null
    },
    name: {
      type: String,
      required: true
    },
    value: {
      type: String,
      required: false,
      default: ""
    }
  }
};
</script>

<style scoped></style>
