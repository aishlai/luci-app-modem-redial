'use strict';
'require view';
'require form';
'require fs';
'require ui';

var PLUGIN_VERSION = 'v1.1.3';

return view.extend({
	load: function() {
		return Promise.all([
			L.resolveDefault(fs.read('/tmp/log/modem_redial.log'), ''),
			L.resolveDefault(fs.exec('/usr/bin/modem_redial', ['--status']), {})
		]);
	},

	render: function(data) {
		var m, s, o;

		m = new form.Map('modem_redial', _('光猫重拨助手') + ' (' + PLUGIN_VERSION + ')',
			_('专为北京联通定制版华为光猫 V271-20 设计，通过控制光猫后台快速切换手动与自动拨号，实现秒级重新拨号换IP，有效解除运营商 UDP QoS 限速与网络阻断。'));

		// 运行状态与操作卡片 (无多余标题，直接平铺展示卡片与按钮)
		s = m.section(form.NamedSection, 'config', 'modem_redial');
		s.anonymous = true;

		o = s.option(form.DummyValue, '_status');
		o.rawhtml = true;
		o.cfgvalue = function() {
			var statusObj = {};
			try {
				var raw = (data[1] && data[1].stdout) ? data[1].stdout : data[1];
				statusObj = JSON.parse(raw || '{}');
			} catch(e) {}
			var currentIP = statusObj.ip || '未知';
			var connStatus = statusObj.status || '未知';
			var triggerMode = statusObj.trigger || '-';
			var wanName = statusObj.wan || '2_INTERNET_R_VID_3961';

			var statusColor = (connStatus === 'Connected' || connStatus === '已连接') ? '#28a745' : ((connStatus === 'Disconnected' || connStatus === '未连接') ? '#dc3545' : (connStatus === '未配置' ? '#6c757d' : '#ffc107'));

			var escapedLog = (data[0] || '暂无执行日志').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

			return '<div style="display:flex;flex-wrap:wrap;gap:12px;margin-bottom:15px;">' +
				'<div style="flex:1 1 180px;background:rgba(0,0,0,0.03);border:1px solid rgba(0,0,0,0.08);border-radius:6px;padding:10px 14px;">' +
					'<div style="font-size:12px;color:#888;">当前公网 IP</div>' +
					'<div id="modem_current_ip" style="font-size:18px;font-weight:600;color:#333;">' + currentIP + '</div>' +
				'</div>' +
				'<div style="flex:1 1 180px;background:rgba(0,0,0,0.03);border:1px solid rgba(0,0,0,0.08);border-radius:6px;padding:10px 14px;">' +
					'<div style="font-size:12px;color:#888;">连接状态</div>' +
					'<div id="modem_conn_status" style="font-size:18px;font-weight:600;color:' + statusColor + ';">' + connStatus + '</div>' +
				'</div>' +
				'<div style="flex:1 1 180px;background:rgba(0,0,0,0.03);border:1px solid rgba(0,0,0,0.08);border-radius:6px;padding:10px 14px;">' +
					'<div style="font-size:12px;color:#888;">当前拨号模式</div>' +
					'<div id="modem_trigger_mode" style="font-size:16px;font-weight:600;color:#333;">' + triggerMode + '</div>' +
				'</div>' +
				'<div style="flex:1 1 180px;background:rgba(0,0,0,0.03);border:1px solid rgba(0,0,0,0.08);border-radius:6px;padding:10px 14px;">' +
					'<div style="font-size:12px;color:#888;">目标 WAN 接口</div>' +
					'<div style="font-size:14px;font-weight:600;color:#333;word-break:break-all;">' + wanName + '</div>' +
				'</div>' +
			'</div>' +
			'<div style="margin: 10px 0;">' +
				'<button type="button" class="btn cbi-button-apply" id="btn_manual_redial" onclick="window.triggerModemRedial()">' +
					'⚡ 立即重拨换IP' +
				'</button>' +
				'&nbsp;&nbsp;' +
				'<button type="button" class="btn cbi-button-reset" onclick="window.refreshModemStatus()">' +
					'🔄 刷新状态' +
				'</button>' +
				'&nbsp;&nbsp;' +
				'<button type="button" class="btn cbi-button-remove" onclick="window.clearModemLog()">' +
					'🗑️ 清空日志' +
				'</button>' +
				'&nbsp;&nbsp;' +
				'<button type="button" class="btn cbi-button-action" id="btn_check_update" onclick="window.checkPluginUpdate()">' +
					'🚀 检查更新' +
				'</button>' +
			'</div>' +
			'<div style="margin-top:10px;">' +
				'<div style="font-size:12px;color:#888;margin-bottom:4px;">实时执行日志 (最近输出):</div>' +
				'<textarea id="modem_redial_log" readonly style="width:100%;height:220px;background:#1e1e1e;color:#d4d4d4;font-family:monospace;padding:8px;border-radius:4px;box-sizing:border-box;resize:vertical;">' +
					escapedLog +
				'</textarea>' +
			'</div>';
		};

		// 基本参数设置
		s = m.section(form.NamedSection, 'config', 'modem_redial', _('参数配置'));
		s.anonymous = true;
		s.addremove = false;

		o = s.option(form.Flag, 'enabled', _('启用插件'));
		o.default = '0';
		o.rmempty = false;

		o = s.option(form.Value, 'router_url', _('光猫后台地址'));
		o.default = '';
		o.placeholder = 'http://192.168.1.1';
		o.rmempty = false;

		o = s.option(form.Value, 'username', _('登录用户名'));
		o.default = '';
		o.placeholder = 'user';
		o.rmempty = false;

		o = s.option(form.Value, 'password', _('登录密码'));
		o.password = true;
		o.default = '';
		o.placeholder = '光猫登录密码';
		o.rmempty = false;

		o = s.option(form.Value, 'wan_name', _('目标 WAN 连接名称'));
		o.default = '2_INTERNET_R_VID_3961';
		o.description = _('光猫后台 WAN 配置中的连接标识 (例如: 2_INTERNET_R_VID_3961)');
		o.rmempty = false;

		o = s.option(form.Value, 'pause_seconds', _('断开等待时间 (秒)'));
		o.datatype = 'uinteger';
		o.default = '3';
		o.description = _('切换为手动拨号后，等待光猫完全下线的暂停时间，默认 3 秒');
		o.rmempty = false;

		// 定时任务
		s = m.section(form.NamedSection, 'config', 'modem_redial', _('定时自动重拨换IP'));
		s.anonymous = true;

		o = s.option(form.Flag, 'cron_enabled', _('启用定时自动重拨'));
		o.default = '0';
		o.rmempty = false;

		o = s.option(form.Value, 'cron_time', _('Cron 表达式'));
		o.depends('cron_enabled', '1');
		o.default = '0 4 * * *';
		o.description = _('标准 Crontab 5位表达式，例如：<code>0 4 * * *</code> (每天凌晨4点重拨换IP)；<code>0 */6 * * *</code> (每6小时重拨一次)');

		// 全局日志轮询函数
		window.startLogPolling = function() {
			var pollCount = 0;
			var maxPolls = 60;

			var btn = document.getElementById('btn_manual_redial');
			if (btn) {
				btn.disabled = true;
				btn.innerText = '⏳ 正在重新拨号中...';
			}

			if (window._modemRedialTimer) {
				clearInterval(window._modemRedialTimer);
				window._modemRedialTimer = null;
			}

			function finishPolling() {
				if (window._modemRedialTimer) {
					clearInterval(window._modemRedialTimer);
					window._modemRedialTimer = null;
				}
				var b = document.getElementById('btn_manual_redial');
				if (b) {
					b.disabled = false;
					b.innerText = '⚡ 立即重拨换IP';
				}
				setTimeout(function() {
					window.refreshModemStatus();
				}, 1200);
			}

			window._modemRedialTimer = setInterval(function() {
				pollCount++;

				var logBox = document.getElementById('modem_redial_log');

				L.resolveDefault(fs.read('/tmp/log/modem_redial.log'), '').then(function(logTxt) {
					if (logBox && logTxt) {
						logBox.value = logTxt;
						logBox.scrollTop = logBox.scrollHeight;
					}

					var isDone = false;
					if (logTxt) {
						if (logTxt.indexOf('重拨换IP流程结束') !== -1 ||
							logTxt.indexOf('释放单用户会话锁') !== -1 ||
							logTxt.indexOf('重新拨号成功') !== -1 ||
							logTxt.indexOf('已有重拨任务在运行中') !== -1 ||
							logTxt.indexOf('超时未检测到') !== -1 ||
							logTxt.indexOf('登录失败') !== -1 ||
							logTxt.indexOf('未找到') !== -1 ||
							logTxt.indexOf('处于禁用状态') !== -1 ||
							logTxt.indexOf('未配置') !== -1 ||
							logTxt.indexOf('Traceback') !== -1) {
							isDone = true;
						}
					}

					// 辅助检查进程状态 (每2秒检查一次)
					if (!isDone && pollCount % 2 === 0 && pollCount >= 4) {
						L.resolveDefault(fs.exec('/usr/bin/modem_redial', ['--status']), {}).then(function(res) {
							try {
								var raw = (res && res.stdout) ? res.stdout : res;
								var s = JSON.parse(raw || '{}');
								if (s.running === false) {
									finishPolling();
								}
							} catch(e) {}
						});
					}

					if (isDone || pollCount >= maxPolls) {
						finishPolling();
					}
				}).catch(function(err) {
					if (pollCount >= maxPolls) {
						finishPolling();
					}
				});
			}, 1000);
		};

		// 挂载全局交互脚本
		window.triggerModemRedial = function() {
			if (!confirm('确定立即触发光猫重新拨号换IP吗？拨号期间宽带会短暂中断 3~5 秒。')) return;

			var btn = document.getElementById('btn_manual_redial');
			if (btn) {
				btn.disabled = true;
				btn.innerText = '⏳ 正在启动任务...';
			}

			var logBox = document.getElementById('modem_redial_log');
			if (logBox) {
				logBox.value = '[*] 正在启动后台重拨换IP任务...\n';
			}

			// 预先写入初始日志行，避免 0 字节导致的 NoDataError，并覆盖上一轮的成功结束标志
			fs.write('/tmp/log/modem_redial.log', '[*] 正在启动后台守护重拨换IP任务...\n').then(function() {
				window.startLogPolling();

				fs.exec('/usr/bin/modem_redial', ['--start']).then(function(res) {
					var stdout = (res && res.stdout) ? res.stdout.trim() : '';
					if (stdout.indexOf('NOT_CONFIGURED') !== -1) {
						if (window._modemRedialTimer) {
							clearInterval(window._modemRedialTimer);
							window._modemRedialTimer = null;
						}
						if (btn) { btn.disabled = false; btn.innerText = '⚡ 立即重拨换IP'; }
						ui.addNotification(null, E('p', '光猫后台地址、用户名或密码未配置，请先保存配置！'));
						return;
					}
					if (stdout.indexOf('ALREADY_RUNNING') !== -1) {
						ui.addNotification(null, E('p', '已有重拨换IP任务正在后台运行中，请勿重复触发！'));
						return;
					}
				}).catch(function(err) {
					// 容错处理：光猫重拨断网瞬间可能伴随短暂网络瞬断，先校验是否已在后台平稳运行
					L.resolveDefault(fs.read('/tmp/log/modem_redial.log'), '').then(function(logTxt) {
						if (logTxt && (logTxt.indexOf('正在') !== -1 || logTxt.indexOf('步骤') !== -1 || logTxt.indexOf('切换') !== -1 || logTxt.indexOf('探测') !== -1 || logTxt.indexOf('重拨') !== -1)) {
							// 守护任务已在平稳推进中，不中断轮询，不弹出误报
							return;
						}
						if (window._modemRedialTimer) {
							clearInterval(window._modemRedialTimer);
							window._modemRedialTimer = null;
						}
						if (btn) {
							btn.disabled = false;
							btn.innerText = '⚡ 立即重拨换IP';
						}
						ui.addNotification(null, E('p', '启动重拨任务失败: ' + (err.message || err)));
					});
				});
			});
		};

		window.refreshModemStatus = function() {
			fs.exec('/usr/bin/modem_redial', ['--status']).then(function(res) {
				try {
					var raw = (res && res.stdout) ? res.stdout : res;
					var data = JSON.parse(raw || '{}');
					var ipEl = document.getElementById('modem_current_ip');
					var statusEl = document.getElementById('modem_conn_status');
					var triggerEl = document.getElementById('modem_trigger_mode');
					if (ipEl) ipEl.innerText = data.ip || '未知';
					if (statusEl) {
						statusEl.innerText = data.status || '未知';
						statusEl.style.color = (data.status === 'Connected' || data.status === '已连接') ? '#28a745' : ((data.status === 'Disconnected' || data.status === '未连接') ? '#dc3545' : '#ffc107');
					}
					if (triggerEl) triggerEl.innerText = data.trigger || '-';

					if (data.running) {
						window.startLogPolling();
					}
				} catch(e) {}
			});
			L.resolveDefault(fs.read('/tmp/log/modem_redial.log'), '').then(function(logTxt) {
				var box = document.getElementById('modem_redial_log');
				if (box && logTxt) {
					box.value = logTxt;
					box.scrollTop = box.scrollHeight;
				}
			});
		};

		window.clearModemLog = function() {
			fs.write('/tmp/log/modem_redial.log', '\n').then(function() {
				var box = document.getElementById('modem_redial_log');
				if (box) box.value = '';
			});
		};

		// 检查 GitHub 最新版本
		window.checkPluginUpdate = function() {
			var btn = document.getElementById('btn_check_update');
			if (btn) {
				btn.disabled = true;
				btn.innerText = '⏳ 正在检查最新版本...';
			}

			fs.exec('/usr/bin/modem_redial', ['--check-update']).then(function(res) {
				if (btn) {
					btn.disabled = false;
					btn.innerText = '🚀 检查更新';
				}

				var raw = (res && res.stdout) ? res.stdout.trim() : '';
				var info = {};
				try {
					info = JSON.parse(raw || '{}');
				} catch(e) {
					ui.addNotification(null, E('p', '解析更新信息失败: ' + raw));
					return;
				}

				if (!info.success) {
					ui.addNotification(null, E('p', '检查更新失败: ' + (info.error || '无法连接 GitHub')));
					return;
				}

				if (!info.has_update) {
					ui.addNotification(null, E('p', '当前已是最新版本 (' + info.current_version + ')，暂无新版本。'), 'info');
					return;
				}

				// 发现新版本，弹出优雅确认弹窗
				var notesContent = info.release_notes ? [
					E('div', { 'style': 'font-size:12px;color:#888;margin-top:10px;margin-bottom:4px;' }, _('更新说明:')),
					E('pre', { 'style': 'background:#f7f7f7;border:1px solid #e8e8e8;padding:8px 12px;border-radius:4px;max-height:160px;overflow-y:auto;white-space:pre-wrap;font-family:monospace;font-size:12px;' }, [ info.release_notes ])
				] : [];

				ui.showModal(_('发现新版本可用'), [
					E('div', { 'style': 'padding:5px 0;' }, [
						E('p', { 'style': 'font-size:15px;font-weight:600;margin-bottom:8px;' }, [
							_('最新版本: '),
							E('span', { 'style': 'color:#1890ff;' }, [ info.latest_version ]),
							_(' (当前版本: ') + info.current_version + ')'
						]),
						E('div', {}, notesContent),
						E('p', { 'style': 'color:#666;font-size:12px;margin-top:10px;' }, _('点击一键升级后，路由器将自动从 GitHub 下载并静默覆盖安装最新版本。')),
						E('div', { 'class': 'right', 'style': 'margin-top:15px;' }, [
							E('button', {
								'class': 'btn cbi-button-reset',
								'click': ui.hideModal
							}, _('稍后再说')),
							' ',
							E('button', {
								'class': 'btn cbi-button-apply',
								'click': function(ev) {
									ui.hideModal();
									window.doPluginUpdate(info.download_url, info.latest_version);
								}
							}, _('🚀 立即一键升级'))
						])
					])
				]);
			}).catch(function(err) {
				if (btn) {
					btn.disabled = false;
					btn.innerText = '🚀 检查更新';
				}
				ui.addNotification(null, E('p', '请求检查更新出错: ' + (err.message || err)));
			});
		};

		// 执行一键升级
		window.doPluginUpdate = function(downloadUrl, newVersion) {
			ui.showModal(_('正在升级插件'), [
				E('div', { 'style': 'text-align:center;padding:25px 15px;' }, [
					E('div', { 'style': 'font-size:32px;margin-bottom:12px;' }, '⏳'),
					E('p', { 'style': 'font-size:15px;font-weight:600;' }, [
						_('正在下载并安装最新版本 ') + (newVersion || '') + ' ...'
					]),
					E('p', { 'style': 'font-size:12px;color:#888;margin-top:6px;' }, _('正在从 GitHub 下载最新 IPK 安装包并执行覆盖安装，请稍候...'))
				])
			]);

			var params = ['--do-update'];
			if (downloadUrl) {
				params.push('--pkg-url');
				params.push(downloadUrl);
			}

			fs.exec('/usr/bin/modem_redial', params).then(function(res) {
				var raw = (res && res.stdout) ? res.stdout.trim() : '';
				var ret = {};
				try {
					ret = JSON.parse(raw || '{}');
				} catch(e) {
					ret = { success: false, error: raw };
				}

				if (ret.success) {
					ui.showModal(_('升级成功'), [
						E('div', { 'style': 'text-align:center;padding:25px 15px;' }, [
							E('div', { 'style': 'font-size:32px;margin-bottom:12px;' }, '🎉'),
							E('p', { 'style': 'font-size:16px;font-weight:600;color:#28a745;' }, _('插件已成功升级至最新版本！')),
							E('p', { 'style': 'font-size:12px;color:#888;margin-top:6px;' }, _('页面将在 3 秒后自动刷新...'))
						])
					]);
					setTimeout(function() {
						location.reload();
					}, 2800);
				} else {
					ui.showModal(_('升级失败'), [
						E('div', { 'style': 'padding:15px 5px;' }, [
							E('p', { 'style': 'color:#dc3545;font-weight:600;font-size:14px;' }, '❌ ' + (ret.error || _('升级过程中发生错误'))),
							E('div', { 'class': 'right', 'style': 'margin-top:15px;' }, [
								E('button', { 'class': 'btn', 'click': ui.hideModal }, _('关闭'))
							])
						])
					]);
				}
			}).catch(function(err) {
				ui.showModal(_('升级发生异常'), [
					E('div', { 'style': 'padding:15px 5px;' }, [
						E('p', { 'style': 'color:#dc3545;font-size:14px;' }, '❌ ' + (err.message || err)),
						E('div', { 'class': 'right', 'style': 'margin-top:15px;' }, [
							E('button', { 'class': 'btn', 'click': ui.hideModal }, _('关闭'))
						])
					])
				]);
			});
		};

		// 若加载时检测到已有重拨任务在运行，自动开启日志轮询
		try {
			var rawInit = (data[1] && data[1].stdout) ? data[1].stdout : data[1];
			var initialStatus = JSON.parse(rawInit || '{}');
			if (initialStatus.running) {
				setTimeout(window.startLogPolling, 500);
			}
		} catch(e) {}

		return m.render();
	}
});
