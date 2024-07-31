<template>
  <div
    class="uk-card uk-card-hover uk-card-small uk-card-default uk-margin"
    :class="{ 'uk-card-secondary': $store.state.darkMode }"
  >
    <div class="uk-card-body">
      <div class="uk-grid-small uk-flex-middle" uk-grid>
        <div class="uk-width-auto">
          <img
            v-if="iconURL"
            style="height:50px"
            :data-src="iconURL"
            :alt="name + ' icon'"
            uk-img
          />
          <span
            v-if="!iconURL"
            class="material-symbols-outlined"
            style="font-size:50px"
          >
            {{ iconName }}
          </span>
        </div>
        <div class="uk-width-expand">
          <h3 class="uk-card-title uk-margin-remove-bottom">{{ name }}</h3>
          <p class="uk-text-meta uk-margin-remove-top">
            <slot name="subtitle"></slot>
          </p>
        </div>
        <div class="uk-width-auto">
          <button class="uk-button" @click="$emit('click')">
            <slot name="buttonText">Launch</slot>
          </button>
        </div>
      </div>
      <slot></slot>
    </div>
  </div>
</template>

<script>
export default {
  name: "ImjoyPluginCard",

  props: {
    name: {
      type: String,
      required: true
    },
    iconURL: {
      type: String,
      required: false,
      default: () => ""
    },
    iconName: {
      type: String,
      required: false,
      default: () => "extension"
    }
  }
};
</script>
