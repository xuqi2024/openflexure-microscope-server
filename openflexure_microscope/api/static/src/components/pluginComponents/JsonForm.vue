<template>
  <div class="uk-padding-small">
    <div class="uk-flex">
      <div class="uk-text-bold uk-text-uppercase uk-width-expand">
        {{ name }}
      </div>
      <a href="#" class="uk-icon uk-width-auto" @click="updateForm()"
        ><i class="material-icons">cached</i></a
      >
    </div>

    <form ref="formContainer" class="uk-form-stacked" @submit.prevent="">
      <div v-for="(field, index) in schema" :key="index">
        <div
          v-if="Array.isArray(field)"
          class="uk-grid-small uk-width-1-1 uk-child-width-expand"
          uk-grid
        >
          <div v-for="(subfield, subindex) in field" :key="subindex">
            <component
              :is="subfield.fieldType"
              v-model="formData[subfield.name]"
              v-bind="subfield"
            >
            </component>
          </div>
        </div>

        <component
          :is="field.fieldType"
          v-model="formData[field.name]"
          v-bind="field"
        >
        </component>
      </div>

      <div v-if="isTask" class="uk-margin">
        <taskSubmitter
          :submit-url="submitApiUri"
          :submit-data="formData"
          :submit-label="submitLabel"
          @submit="onTaskSubmit"
          @response="onTaskResponse"
          @error="onTaskError"
        >
        </taskSubmitter>
      </div>

      <div v-else class="uk-margin">
        <button
          type="button"
          class="uk-button uk-button-primary uk-width-1-1"
          @click="newQuickRequest(formData)"
        >
          {{ submitLabel }}
        </button>
      </div>
    </form>
  </div>
</template>

<script>
import axios from "axios";

import numberInput from "../fieldComponents/numberInput";
import selectList from "../fieldComponents/selectList";
import textInput from "../fieldComponents/textInput";
import htmlBlock from "../fieldComponents/htmlBlock";
import radioList from "../fieldComponents/radioList";
import checkList from "../fieldComponents/checkList";
import tagList from "../fieldComponents/tagList";
import keyvalList from "../fieldComponents/keyvalList";

import taskSubmitter from "../genericComponents/taskSubmitter";

export default {
  name: "JsonForm",

  components: {
    numberInput,
    selectList,
    textInput,
    htmlBlock,
    radioList,
    checkList,
    tagList,
    keyvalList,
    taskSubmitter
  },

  props: {
    name: {
      type: String,
      required: false,
      default: "Plugin"
    },
    schema: {
      type: Array,
      required: true
    },
    route: {
      type: String,
      required: true
    },
    isTask: {
      type: Boolean,
      required: false,
      default: false
    },
    submitLabel: {
      type: String,
      required: false,
      default: "Submit"
    },
    emitOnResponse: {
      type: String,
      required: false,
      default: null
    }
  },

  emits: ["reload-forms"],

  data: function() {
    return {
      formData: {}
    };
  },

  computed: {
    pluginApiUri: function() {
      return `${this.$store.getters.baseUri}/api/v2/extensions`;
    },

    submitApiUri: function() {
      return this.pluginApiUri + this.route;
    }
  },

  watch: {
    // Whenever the form schema updates, re-check server for field values
    schema: function() {
      this.updateFormValues();
    }
  },

  created() {
    this.initialiseFormData();
  },

  methods: {
    initialiseFormData() {
      /* 
      This function initialises the form data.
      Limitations in Vue mean that newly created formData properties are not reactive.
      GETting formData values from the server creates the properties, but the form components
      don't get updated because of this limitation.
      Here, we step through the form schema, and properly create reactive properties for each component.
      */
      for (const field of this.schema) {
        if (Array.isArray(field)) {
          var defaultValue; // Initial value of the form component
          for (const subfield of field) {
            // If a default value is given in the schema, use this
            if (subfield.value) {
              defaultValue = subfield.value;
            } else if (subfield.default) {
              defaultValue = subfield.default;
            } else {
              defaultValue = null;
            }
            this.$set(this.formData, subfield.name, defaultValue);
          }
        } else {
          // If a default value is given in the schema, use this
          if (field.value) {
            defaultValue = field.value;
          } else if (field.default) {
            defaultValue = field.default;
          } else {
            defaultValue = null;
          }
          this.$set(this.formData, field.name, defaultValue);
        }
      }
    },

    updateFormValues() {
      for (const field of this.schema) {
        if (Array.isArray(field)) {
          for (const subfield of field) {
            // If a default value is given in the schema, use this
            if (subfield.value) {
              this.$set(this.formData, subfield.name, subfield.value);
            }
          }
        } else {
          if (field.value) {
            this.$set(this.formData, field.name, field.value);
          }
        }
      }
    },

    updateForm() {
      this.$emit("reload-forms");
    },

    onSubmissionCompleted: function() {
      if (this.emitOnResponse) {
        this.$emitter.emit(this.emitOnResponse);
      }
      this.updateForm();
    },

    newQuickRequest: function(params) {
      // Send a quick request
      axios
        .post(this.submitApiUri, params)
        .then(() => {
          // Do all the finished request stuff
          this.onSubmissionCompleted();
        })
        .catch(error => {
          this.modalError(error); // Let mixin handle error
        });
    },

    onTaskSubmit: function() {},

    onTaskResponse: function() {
      // Do all the finished request stuff
      this.onSubmissionCompleted();
    },

    onTaskError: function(error) {
      this.modalError(error);
    }
  }
};
</script>

<style scoped>
.flex-container {
  display: flex;
}

.flex-container > div {
  flex-basis: 100%;
}
</style>
