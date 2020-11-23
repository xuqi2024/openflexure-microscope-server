<template>
  <div>
    <label class="uk-form-label">{{ label }}</label>

    <input
      class="uk-input uk-form-small"
      type="number"
      :name="name"
      :value="value"
      :placeholder="placeholder"
      v-bind="$attrs"
      @input="$emit('input', Number($event.target.value))"
    />
  </div>
</template>

<script>
export default {
  name: "NumberInput",

  props: {
    value: {
      type: Number,
      required: false,
      default: 0
    },
    placeholder: {
      type: Number,
      required: false,
      default: 0
    },
    name: {
      type: String,
      required: true
    },
    label: {
      type: String,
      required: true
    }
  },

  emits: ["input"]
};
</script>

<style scoped></style>
