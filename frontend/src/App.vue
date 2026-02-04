
<template>
  <el-container class="layout">
    <el-header class="header">
      <div class="brand">智能组卷系统 V3</div>
      <div class="right">前后端分离 · Vue + Flask</div>
    </el-header>

    <el-container>
      <el-aside class="aside" width="220px">
        <el-menu router :default-active="$route.path" class="menu">
          <el-menu-item index="/dicts">基础字典</el-menu-item>
          <el-menu-item index="/ai-review">AI校验</el-menu-item>
          <el-menu-item index="/textbooks">教材管理</el-menu-item>
          <el-menu-item index="/questions">题库管理</el-menu-item>
          <el-menu-item index="/paper-generate">智能组卷</el-menu-item>
          <el-menu-item index="/papers">试卷管理</el-menu-item>
          <el-menu-item index="/answer-sheets">答题卡</el-menu-item>
        </el-menu>
      </el-aside>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.layout {
  min-height: 100vh;
}

.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--el-border-color);
}

.brand {
  font-weight: 700;
  letter-spacing: 0.5px;
}

.right {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.aside {
  border-right: 1px solid var(--el-border-color);
}

.menu {
  border-right: none;
}

.main {
  padding: 16px;
}
</style>
