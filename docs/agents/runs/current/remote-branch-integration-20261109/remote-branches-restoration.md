# 远程分支清理恢复记录

2026-11-09 用户明确批准后执行。以下九个分支在删除前均已是 origin/master 的祖先，且未被开放 PR 引用。master 与 develop 未因清理改变；release tags 未删除。

本地另保存 `refs/codex-backups/remote-branches/20261109/<原分支名>`。
需要恢复时从本仓库执行相应一条命令：

```bash
git push origin c2199b1fa9a2ba739f555ae4b68d736d1ebbd97c:refs/heads/codex/v2.0.0-release-closeout
git push origin 8c23c85afb83efc04a20a6543391a0afbdef6a00:refs/heads/docs-refactor-2026-01
git push origin 360c5707dd5b1e92c463326de3fe6ea5e963fc89:refs/heads/feat/daq-adapter-and-cache-management
git push origin 7c227d7d117ad100a605c850ebe8ed6aee763f08:refs/heads/feat/waveform-width-plugin
git push origin 73ee9fd096448d59bf185d87914b5ac948fffe8a:refs/heads/release/v1.0.0
git push origin 715c8ce35a93d04f7641b4b149e56b7be6ea01e4:refs/heads/release/v1.5.0
git push origin 972c7ba8c4ba88634f448f27171cef6906189c72:refs/heads/release/v2.0.0
git push origin 811eb1eeb7f6fe50f4041988715e0de1a297e91f:refs/heads/wip/core
git push origin 9f6e52822a86cd960fd6aa058511322bd8a452b6:refs/heads/wip/plugins
```

执行使用原始头 SHA 的 force-with-lease 与 atomic push；九个删除均成功。保留有独立提交的旧发布分支，未把旧版本元数据强行合入当前开发线。
