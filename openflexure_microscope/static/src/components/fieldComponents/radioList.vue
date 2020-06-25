<template>
  <div>
    <label>{{ label }}</label>

    <div class="uk-form-controls">
      <div v-for="option in options" :key="option">
        <label
          ><input
            class="uk-radio"
            type="radio"
            :name="name"
            :value="option"
            :checked="value == option"
            @input="$emit('input', $event.target.value)"
          />
          {{ option }}</label
        >
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "RadioList",

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
