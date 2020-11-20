<template>
  <div>
    <label>{{ label }}</label>

    <div class="uk-form-controls">
      <div v-for="option in options" :key="option">
        <label>
          <input
            class="uk-checkbox"
            type="checkbox"
            :value="option"
            :checked="value && value.includes(option)"
            v-bind="$attrs"
            @change="updateValue($event.target)"
          />
          {{ option }}
        </label>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: "CheckList",

  props: {
    value: {
      type: Array,
      required: false,
      default: function() {
        return [];
      }
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
  },

  methods: {
    updateValue(target) {
      let newSelected = this.value != null ? [...this.value] : []; // Clone value array

      if (target.checked) {
        if (!newSelected.includes(target.value)) {
          newSelected.push(target.value);
        }
      } else {
        if (newSelected.includes(target.value)) {
          newSelected = newSelected.filter(function(value) {
            return value != target.value;
          });
        }
      }
      this.$emit("input", newSelected);
    }
  }
};
</script>

<style scoped></style>
