<template>
  <footer class="site-footer">
    <span>Campus Universitário Darcy Ribeiro · Brasília-DF · CEP 70910-900</span>
    <span>
      <a href="https://software.unb.br" target="_blank" rel="noopener">software.unb.br</a>
      &nbsp;·&nbsp;
      Copyright &copy; {{ year }} Universidade de Brasília
    </span>
  </footer>
</template>

<script setup lang="ts">
const year = new Date().getFullYear()
</script>

<style scoped>
.site-footer {
  background: var(--color-navy);
  color: rgba(255, 255, 255, 0.55);
  font-size: 11px;
  padding: 8px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-shrink: 0;
}
.site-footer a { color: rgba(255, 255, 255, 0.75); text-decoration: none; }
.site-footer a:hover { color: #fff; }

@media (max-width: 600px) {
  .site-footer { flex-direction: column; gap: 2px; text-align: center; }
}
</style>
