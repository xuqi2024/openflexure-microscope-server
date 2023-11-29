<template>
    <div>
      <label class="uk-form-label">{{ label }}</label>
      <div class="input-and-buttons-container" v-if="dataType=='number_array'">
        <input
          v-for="i in value.length"
          :key="i"
          v-model="value[i - 1]"
          class="uk-form-small numeric-setting-line-input"
          type="number"
          @focusin="focusIn"
          @focusout="focusOut"
          @keydown="keyDown"
        />
        <a class="button-next-to-input" @click="readProperty">
          <i class="material-icons">refresh</i>
        </a>
      </div>
      <div v-else >
        {{ value }}
      </div>
    </div>
</template>
  
<script>
import axios from "axios";

export default {
    name: "PropertyControl",

    props: {
        propertyName: {
        type: String,
        required: true
        },
        consumedThing: {
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
        value: {},
        valueOnEnter: undefined,
        focused: false,
        };
    },

    computed: {
        readBack: function() {
        return this.readBackDelay !== undefined;
        }/*,
        dataType: function() {
            let prop = this.consumedThing.properties[this.propertyName]
            const num_types = ["integer", "float", "number"];
            if (prop.type in num_types) {
                return "number";
            }
            if (prop.type == "array") {
                if (prop.items in num_types){
                return "number_array";
                }
                if (Array.isArray(prop.items)) {
                if (prop.items.every((t) => t in num_types)){
                return "number_array";
                }
            }
            if (prop.type == "object") {
                let numeric = true;
                for (let key in prop.properties) {
                    if (!(prop.properties[key].type in num_types)) {
                        numeric = false;
                        break;
                    }
                }
                if (numeric) {
                    return "number_object";
                }
            }
            return "other";
        }*/
    },

    mounted: function() {
        this.readProperty();
    },

    methods: {
        readProperty: async function() {
            let response = await axios.get(this.propertyUrl);
            this.value = response.data;
            console.log("Read property", this.propertyUrl, response.data);
            return response.data;
        },
        writeProperty: async function() {
            try {
                let requestedValue = this.value;
                await axios.post(this.propertyUrl, requestedValue);
                if (this.readBack) {
                    await new Promise(r => setTimeout(r, this.readBackDelay));
                    let newVal = await this.readProperty();
                    if (newVal == requestedValue) {
                        await this.modalNotify(`Set ${this.label} to ${newVal}.`);
                    } else {
                        await this.modalNotify(
                            `Set ${this.label} to ${newVal} (requested ${requestedValue}).`
                        );
                    }
                } else {
                    await this.modalNotify(`Set ${this.label} to ${this.value}.`);
                }
            } catch (error) {
                this.modalError(error); // Let mixin handle error
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
}
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
