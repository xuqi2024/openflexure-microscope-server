<template>
  <div>
    <label v-if="dataType == 'number'" class="uk-form-label"
      >{{ label }}
      <div class="input-and-buttons-container">
        <input
          v-model="value"
          class="uk-form-small numeric-setting-line-input"
          type="number"
          @focusin="focusIn"
          @focusout="focusOut"
          @keydown="keyDown"
        />
        <a class="button-next-to-input" @click="readProperty">
          <span class="material-symbols-outlined">refresh</span>
        </a>
      </div>
    </label>
    <div v-if="dataType == 'boolean'" class="input-and-buttons-container">
      <label class="uk-form-label numeric-setting-line-input">
        <input
          ref="checkbox"
          v-model="value"
          class="uk-checkbox"
          type="checkbox"
          @change="writeProperty"
        />
        {{ label }}
      </label>
      <a class="button-next-to-input" @click="readProperty">
        <span class="material-symbols-outlined">refresh</span>
      </a>
    </div>
    <label v-if="dataType == 'number_array'" class="uk-form-label"
      >{{ label }}
      <div class="input-and-buttons-container">
        <input
          v-for="i in valueLength"
          :key="i"
          v-model="value[i - 1]"
          class="uk-form-small numeric-setting-line-input"
          type="number"
          @focusin="focusIn"
          @focusout="focusOut"
          @keydown="keyDown"
        />
        <a class="button-next-to-input" @click="readProperty">
          <span class="material-symbols-outlined">refresh</span>
        </a>
      </div>
    </label>
    <label v-if="dataType == 'number_object'" class="uk-form-label"
      >{{ label }}
      <div class="input-and-buttons-container">
        <input
          v-for="(_v, key) in value"
          :key="key"
          v-model="value[key]"
          class="uk-form-small numeric-setting-line-input"
          type="number"
          @focusin="focusIn"
          @focusout="focusOut"
          @keydown="keyDown"
        />
        <a class="button-next-to-input" @click="readProperty">
          <span class="material-symbols-outlined">refresh</span>
        </a>
      </div>
    </label>
    <label v-if="dataType == 'other'" class="uk-form-label"
      >{{ label }}
      <div class="input-and-buttons-container">
        <input
          :value="value"
          class="uk-form-small numeric-setting-line-input"
          type="text"
          disabled="true"
        />
      </div>
    </label>
  </div>
</template>

<script>
export default {
  name: "PropertyControl",

  props: {
    label: {
      type: String,
      default: ""
    },
    propertyName: {
      type: String,
      required: true
    },
    thingName: {
      type: String,
      required: true
    },
    readBackDelay: {
      type: Number,
      default: undefined,
      required: false
    }
  },

  data: () => {
    return {
      value: undefined,
      valueOnEnter: undefined,
      focused: false
    };
  },

  computed: {
    valueLength: function() {
      if (this.dataType == "number_array") {
        if (this.value == undefined) {
          return 0;
        }
        return this.value.length;
      } else {
        return 1;
      }
    },
    readBack: function() {
      return this.readBackDelay !== undefined;
    },
    propertyDescription: function() {
      try {
        return this.thingDescription(this.thingName).properties[
          this.propertyName
        ];
      } catch (error) {
        return undefined;
      }
    },
    dataType: function() {
      let prop = this.propertyDescription;
      if (prop == undefined) {
        return "undefined";
      }
      const num_types = ["integer", "float", "number"];
      if (num_types.includes(prop.type)) {
        return "number";
      }
      if (prop.type == "array") {
        if (num_types.includes(prop.items.type)) {
          return "number_array";
        }
        if (Array.isArray(prop.items)) {
          if (prop.items.every(t => num_types.includes(t.type))) {
            return "number_array";
          }
        }
      }
      if (prop.type == "boolean") {
        return "boolean";
      }
      if (prop.type == "object") {
        let numeric = true;
        for (let key in prop.properties) {
          if (!num_types.includes(prop.properties[key].type)) {
            numeric = false;
            break;
          }
        }
        if (numeric) {
          return "number_object";
        }
      }
      return "other";
    }
  },

  watch: {
    propertyDescription: function() {
      // Ensure we read the property once the URL is known
      this.readProperty();
    }
  },

  mounted: function() {
    // Read the property when we're mounted - usually this won't
    // work because the URL isn't set yet. However, it's helpful if
    // the app is reloaded (e.g. from a dev server).
    if (this.value == undefined) {
      this.readProperty();
    }
  },

  methods: {
    readProperty: async function() {
      let data = await this.readThingProperty(
        this.thingName,
        this.propertyName
      );
      this.value = data;
      return data;
    },
    writeProperty: async function() {
      try {
        let requestedValue = this.value;
        console.log("writing", requestedValue);
        await this.writeThingProperty(
          this.thingName,
          this.propertyName,
          requestedValue
        );
        if (this.readBack) {
          await new Promise(r => setTimeout(r, this.readBackDelay));
          let newVal = await this.readProperty();
          if (newVal == requestedValue) {
            await this.modalNotify(`Set ${this.label}`);
          } else {
            await this.modalNotify(`Set ${this.label}`);
          }
        } else {
          await this.modalNotify(`Set ${this.label}`);
        }
      } catch (error) {
        this.modalError(error); // Let mixin handle error
      }
    },
    checkboxUpdated: function() {
      if (this.value != this.$refs.checkbox.checked) {
        this.value = this.$refs.checkbox.checked;
        this.writeProperty();
      }
    },
    focusIn: function(event) {
      this.valueOnEnter = event.target.value;
    },
    focusOut: function(event) {
      if (this.valueOnEnter != event.target.value) {
        this.writeProperty(event.target.value);
      }
    },
    keyDown: function(event) {
      // Pressing enter should set the property, whether or not we think it's changed.
      if (event.keyCode == 13) {
        this.writeProperty();
      }
    }
  }
};
</script>

<style scoped>
.input-and-buttons-container {
  display: flex;
  flex-flow: row wrap;
  justify-content: flex-start;
  align-content: stretch;
  align-items: center;
  width: 100%;
}
.numeric-setting-line-input {
  flex-grow: 1;
  margin-left: 5px;
  margin-right: 5px;
  width: 6em;
}
.button-next-to-input {
  flex-grow: 0;
  padding-left: 5px;
  padding-right: 5px;
  vertical-align: middle;
  cursor: pointer;
}
</style>
