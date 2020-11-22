<template>
  <div>
    <form @submit.prevent="handleMetadataSubmit">
      <div class="uk-margin-remove uk-flex uk-flex-middle">
        <div
          class="uk-margin-remove-top uk-padding-remove uk-grid-small uk-width-expand"
          uk-grid
        >
          <div class="uk-margin-remove uk-width-1-2">
            <input
              ref="textboxKey"
              v-model="newMetadata.key"
              class="uk-input uk-form-width-small uk-form-small"
              type="text"
              name="flavor"
              placeholder="Key"
            />
          </div>
          <div class="uk-margin-remove uk-width-1-2">
            <input
              v-model="newMetadata.value"
              class="uk-input uk-form-width-small uk-form-small"
              type="text"
              name="flavor"
              placeholder="Value"
              @keyup.enter="handleMetadataSubmit()"
            />
          </div>
        </div>

        <a
          href="#"
          class="uk-icon uk-margin-left"
          @click="handleMetadataSubmit()"
          ><i class="material-icons">add_circle</i></a
        >
      </div>
    </form>

    <div
      v-for="(val, key) in value"
      :key="key"
      class="uk-width-1-1 uk-margin-small uk-margin-remove-left uk-margin-remove-right uk-flex uk-flex-middle"
    >
      <div class="uk-margin-remove-top uk-padding-remove uk-width-expand">
        <labelInput
          :name="key"
          :label="key"
          :value="value[key]"
          @input="value[key] = $event"
        />
      </div>
      <a href="#" class="uk-icon uk-width-auto" @click="delMetadataKey(key)"
        ><i class="material-icons">delete</i></a
      >
    </div>
  </div>
</template>

<script>
import labelInput from "../fieldComponents/labelInput";

export default {
  name: "KeyvalList",

  components: {
    labelInput,
  },

  props: {
    value: {
      type: Object,
      required: true,
    },
  },

  data: function () {
    return {
      newMetadata: {
        key: "",
        value: "",
      },
    };
  },

  methods: {
    handleMetadataSubmit: function () {
      const newSelected = {};

      if (this.value != null) {
        Object.assign(newSelected, this.value);
      }

      newSelected[this.newMetadata.key] = this.newMetadata.value;
      this.newMetadata.key = "";
      this.newMetadata.value = "";

      this.$emit("input", newSelected);

      // Move focus back to key textbox
      this.$refs.textboxKey.focus();
    },

    delMetadataKey: function (key) {
      const newSelected = {};

      if (this.value != null) {
        Object.assign(newSelected, this.value);
      }

      this.$delete(newSelected, key);

      this.$emit("input", newSelected);
    },

    modifyValue: function (e, v) {
      console.log(e);
      console.log(v);
    },
  },
};
</script>

<style scoped></style>
