<template>
  <div>
    <label class="uk-form-label uk-text-bold">{{ label }}</label>

    <div
      uk-tooltip="title: Click to edit value; delay: 250"
      @click="setEditing(true)"
    >
      <div v-show="editing == false">
        <label> {{ value }} </label>
      </div>

      <input
        v-show="editing == true"
        ref="textinput"
        class="uk-input uk-form-small"
        type="text"
        :name="name"
        :value="value"
        autofocus
        @blur="setEditing(false)"
        @keyup.enter="setEditing(false)"
        @input="$emit('input', $event.target.value)"
      />
    </div>
  </div>
</template>

<script>
export default {
  name: "LabelInput",

  props: {
    label: {
      type: String,
      required: true,
    },
    name: {
      type: String,
      required: true,
    },
    value: {
      type: String,
      required: true,
    },
  },

  data: function () {
    return {
      editing: false,
    };
  },

  methods: {
    setEditing(editing) {
      this.editing = editing;
      if (editing == true) {
        this.$nextTick(() => this.$refs.textinput.focus());
      }
    },
  },
};
</script>

<style scoped></style>
