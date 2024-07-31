<template>
  <div>
    <label class="uk-form-label">{{ label }}</label>

    <select
      class="uk-select uk-form-small"
      :value="value"
      v-bind="$attrs"
      @input="$emit('input', $event.target.value)"
    >
      <option v-for="option in options" :key="option">
        {{ option }}
      </option>
    </select>
  </div>
</template>

<script>
export default {
  name: "SelectList",

  props: {
    value: {
      type: String,
      required: false,
      default: ""
    },
    options: {
      type: Array,
      required: true
    },
    name: {
      type: String,
      required: true
    },
    label: {
      type: String,
      required: true
    }
  }
};
</script>

<style scoped></style>
