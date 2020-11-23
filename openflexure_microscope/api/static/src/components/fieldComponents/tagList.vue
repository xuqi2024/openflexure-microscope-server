<template>
  <div>
    <form @submit.prevent="handleTagSubmit">
      <div class="uk-margin-small uk-flex uk-flex-middle">
        <div class="uk-margin-remove-top uk-width-expand">
          <div class="uk-inline uk-width-1-1">
            <span class="uk-form-icon"
              ><i class="material-icons">label</i></span
            >
            <input
              v-model="newTag"
              class="uk-input uk-form-small"
              type="text"
              name="flavor"
              placeholder="Tag"
            />
          </div>
        </div>

        <a href="#" class="uk-icon uk-margin-left" @click="handleTagSubmit()"
          ><i class="material-icons">add_circle</i></a
        >
      </div>
    </form>

    <span
      v-for="tag in value"
      :key="tag"
      class="uk-label uk-margin-small-right deletable-label"
      @click="delTag(tag)"
    >
      {{ tag }}
    </span>
  </div>
</template>

<script>
export default {
  name: "TagList",

  props: {
    value: {
      type: Array,
      required: true
    }
  },

  emits: ["input"],

  data: function() {
    return {
      newTag: ""
    };
  },

  methods: {
    handleTagSubmit: function() {
      var newSelected = this.value != null ? [...this.value] : []; // Clone value array

      newSelected.push(this.newTag);
      this.newTag = "";

      this.$emit("input", newSelected);
    },

    delTag: function(tag) {
      var newSelected = this.value != null ? [...this.value] : []; // Clone value array

      if (newSelected.includes(tag)) {
        newSelected = newSelected.filter(function(value) {
          return value != tag;
        });
      }

      this.$emit("input", newSelected);
    }
  }
};
</script>

<style scoped></style>
