import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import 'uplot/dist/uPlot.min.css';
import './styles.css';

createApp(App).use(createPinia()).mount('#app');
