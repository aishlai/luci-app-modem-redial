'use strict';
'require view';
'require form';
'require fs';
'require ui';

var PLUGIN_VERSION = 'v1.5.7';

return view.extend({
	handleSaveApply: function(ev, mode) {
		return this.super('handleSaveApply', [ev, mode]).then(function() {
			return fs.exec('/etc/init.d/modem_redial', ['restart']);
		});
	},

	load: function() {
		return Promise.all([
			L.resolveDefault(fs.read('/tmp/log/modem_redial.log'), ''),
			L.resolveDefault(fs.exec('/usr/bin/modem_redial', ['--status']), {}),
			L.resolveDefault(fs.read('/etc/modem_redial_qos.log'), ''),
			L.resolveDefault(fs.read('/tmp/log/modem_redial_live_qos.log'), '')
		]);
	},

	render: function(data) {
		var m, s1, s2, o;

		// 1. 顶部标题与插件说明
		m = new form.Map('modem_redial', _('光猫重拨助手') + ' (' + PLUGIN_VERSION + ')',
			_('专为北京联通定制版华为光猫 V271-20 设计，通过控制光猫后台快速切换手动与自动拨号，实现秒级重新拨号换IP，有效解除运营商 UDP QoS 限速与网络阻断。'));

		// 2. 光猫状态区 (单独拎出，放在说明正下方，无标题)
		s1 = m.section(form.NamedSection, 'config', 'modem_redial');
		s1.anonymous = true;
		s1.addremove = false;

		o = s1.option(form.DummyValue, '_status');
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

			var statusColor = (connStatus === 'Connected' || connStatus === '已连接') ? '#28a745' : ((connStatus === 'Disconnected' || connStatus === '未连接') ? '#dc3545' : (connStatus === '未配置' || connStatus === '未启用' ? '#6c757d' : '#ffc107'));

			return '<div style="display:flex;flex-wrap:wrap;gap:12px;margin-bottom:15px;margin-top:5px;">' +
				'<div style="flex:1 1 180px;background:rgba(0,0,0,0.03);border:1px solid rgba(0,0,0,0.08);border-radius:6px;padding:12px 14px;">' +
					'<div style="font-size:12px;color:#888;">' + _('当前公网 IP') + '</div>' +
					'<div id="modem_current_ip" style="font-size:18px;font-weight:600;color:#333;margin-top:2px;">' + currentIP + '</div>' +
				'</div>' +
				'<div style="flex:1 1 180px;background:rgba(0,0,0,0.03);border:1px solid rgba(0,0,0,0.08);border-radius:6px;padding:12px 14px;">' +
					'<div style="font-size:12px;color:#888;">' + _('连接状态') + '</div>' +
					'<div id="modem_conn_status" style="font-size:18px;font-weight:600;color:' + statusColor + ';margin-top:2px;">' + connStatus + '</div>' +
				'</div>' +
				'<div style="flex:1 1 180px;background:rgba(0,0,0,0.03);border:1px solid rgba(0,0,0,0.08);border-radius:6px;padding:12px 14px;">' +
					'<div style="font-size:12px;color:#888;">' + _('当前拨号模式') + '</div>' +
					'<div id="modem_trigger_mode" style="font-size:16px;font-weight:600;color:#333;margin-top:2px;">' + triggerMode + '</div>' +
				'</div>' +
				'<div style="flex:1 1 180px;background:rgba(0,0,0,0.03);border:1px solid rgba(0,0,0,0.08);border-radius:6px;padding:12px 14px;">' +
					'<div style="font-size:12px;color:#888;">' + _('目标 WAN 接口') + '</div>' +
					'<div style="font-size:14px;font-weight:600;color:#333;word-break:break-all;margin-top:2px;">' + wanName + '</div>' +
				'</div>' +
			'</div>' +
			'<div style="display:flex;align-items:center;flex-wrap:wrap;gap:8px;margin-top:15px;margin-bottom:8px;">' +
				'<button type="button" class="btn cbi-button-apply" id="btn_manual_redial" onclick="window.triggerModemRedial()">' +
					'⚡ ' + _('立即重拨号换IP') +
				'</button>' +
				'<button type="button" class="btn cbi-button-reset" id="btn_refresh_status" onclick="window.refreshModemStatus(true)">' +
					'🔄 ' + _('刷新状态') +
				'</button>' +
				'<button type="button" class="btn cbi-button-action" onclick="window.showLogModal(false)">' +
					'📜 ' + _('查看日志') +
				'</button>' +
				'<button type="button" class="btn cbi-button-neutral" id="btn_check_update" onclick="window.checkPluginUpdate(false)">' +
					'🚀 ' + _('检查更新') +
				'</button>' +
				'<span id="check_update_tip" style="margin-left:5px;vertical-align:middle;display:inline-block;"></span>' +
			'</div>';
		};

		// 3. 新区块：以 Tab 形式构建「光猫配置」「定时重拨」「监测重拨」「消息推送」
		s2 = m.section(form.NamedSection, 'config', 'modem_redial');
		s2.anonymous = true;
		s2.addremove = false;

		// 注册 4 个 Tab (不含多余说明描述)
		s2.tab('config', _('光猫配置'));
		s2.tab('cron', _('定时重拨'));
		s2.tab('qos', _('监测重拨'));
		s2.tab('notify', _('消息推送'));

		// ------------------ Tab 1: 光猫配置 ------------------
		o = s2.taboption('config', form.Flag, 'enabled', _('启用插件'));
		o.default = '0';
		o.rmempty = false;
		o.description = _('开启或关闭光猫重拨助手全部自动化功能。');

		o = s2.taboption('config', form.Value, 'router_url', _('光猫后台地址'));
		o.default = '';
		o.placeholder = 'http://192.168.1.1';
		o.rmempty = false;

		o = s2.taboption('config', form.Value, 'username', _('登录用户名'));
		o.default = '';
		o.placeholder = 'user';
		o.rmempty = false;

		o = s2.taboption('config', form.Value, 'password', _('登录密码'));
		o.password = true;
		o.default = '';
		o.placeholder = '光猫登录密码';
		o.rmempty = false;

		o = s2.taboption('config', form.Value, 'wan_name', _('目标 WAN 连接名称'));
		o.default = '2_INTERNET_R_VID_3961';
		o.description = _('光猫后台 WAN 配置中的连接标识 (例如: 2_INTERNET_R_VID_3961)');
		o.rmempty = false;

		o = s2.taboption('config', form.Value, 'pause_seconds', _('断开等待时间 (秒)'));
		o.datatype = 'uinteger';
		o.default = '3';
		o.description = _('切换为手动拨号后，等待光猫完全下线的暂停时间，默认 3 秒');
		o.rmempty = false;

		// ------------------ Tab 2: 定时重拨 ------------------
		o = s2.taboption('cron', form.DummyValue, '_disabled_cron');
		o.depends('enabled', '0');
		o.rawhtml = true;
		o.cfgvalue = function() {
			return '<div style="background:rgba(0,0,0,0.02);border:1px dashed #d9d9d9;border-radius:6px;padding:24px 16px;text-align:center;margin:12px 0;">' +
				'<div style="font-size:32px;margin-bottom:8px;">⏸️</div>' +
				'<div style="font-size:16px;font-weight:600;color:#666;">' + _('插件当前处于关闭状态') + '</div>' +
				'<div style="font-size:13px;color:#999;margin-top:6px;">' + _('请先在「光猫配置」标签页中开启「启用插件」并保存应用。') + '</div>' +
			'</div>';
		};

		o = s2.taboption('cron', form.Flag, 'cron_enabled', _('启用定时自动重拨'));
		o.depends('enabled', '1');
		o.default = '0';
		o.rmempty = false;
		o.retain = true;
		o.description = _('开启后路由器将按设定的计划周期自动触发光猫重新拨号换 IP。');

		o = s2.taboption('cron', form.Value, 'cron_time', _('Cron 表达式'));
		o.depends({ 'enabled': '1', 'cron_enabled': '1' });
		o.default = '0 4 * * *';
		o.description = _('标准 Crontab 5位表达式，例如：<code>0 4 * * *</code> (每天凌晨4点重拨换IP)；<code>0 */6 * * *</code> (每6小时重拨一次)');
		o.retain = true;

		// ------------------ Tab 3: 监测重拨 ------------------
		o = s2.taboption('qos', form.DummyValue, '_disabled_qos');
		o.depends('enabled', '0');
		o.rawhtml = true;
		o.cfgvalue = function() {
			return '<div style="background:rgba(0,0,0,0.02);border:1px dashed #d9d9d9;border-radius:6px;padding:24px 16px;text-align:center;margin:12px 0;">' +
				'<div style="font-size:32px;margin-bottom:8px;">⏸️</div>' +
				'<div style="font-size:16px;font-weight:600;color:#666;">' + _('插件当前处于关闭状态') + '</div>' +
				'<div style="font-size:13px;color:#999;margin-top:6px;">' + _('请先在「光猫配置」标签页中开启「启用插件」并保存应用。') + '</div>' +
			'</div>';
		};

		o = s2.taboption('qos', form.Flag, 'udp_watchdog_enabled', _('启用 UDP 连通性监测'));
		o.depends('enabled', '1');
		o.default = '0';
		o.rmempty = false;
		o.retain = true;
		o.description = _('后台定期测试多个可靠公共节点的 UDP 双向通讯。当全部目标 UDP 均无法连通（疑似被运营商 QoS 限制/断流）时，自动触发光猫重拨换 IP。');

		o = s2.taboption('qos', form.Value, 'udp_check_interval', _('检测间隔时间 (秒)'));
		o.depends({ 'enabled': '1', 'udp_watchdog_enabled': '1' });
		o.datatype = 'uinteger';
		o.default = '60';
		o.placeholder = '60';
		o.description = _('每隔多少秒执行一次 UDP 连通性检测，默认 60 秒（推荐 60 ~ 300 秒）。');
		o.rmempty = false;
		o.retain = true;

		o = s2.taboption('qos', form.Value, 'udp_fail_threshold', _('连续失败重拨阈值'));
		o.depends({ 'enabled': '1', 'udp_watchdog_enabled': '1' });
		o.datatype = 'uinteger';
		o.default = '2';
		o.placeholder = '2';
		o.description = _('连续多少次检测全部目标均不通时才触发重拨，避免偶发网络抖动误触发，默认 2 次。');
		o.rmempty = false;
		o.retain = true;

		o = s2.taboption('qos', form.Value, 'udp_cooldown', _('重拨后冷却时间 (秒)'));
		o.depends({ 'enabled': '1', 'udp_watchdog_enabled': '1' });
		o.datatype = 'uinteger';
		o.default = '180';
		o.placeholder = '180';
		o.description = _('触发重拨换 IP 成功后，暂停检测的冷却时间，给新网络足够的稳定时间，默认 180 秒。');
		o.rmempty = false;
		o.retain = true;

		o = s2.taboption('qos', form.DynamicList, 'udp_targets', _('UDP 检测目标列表'));
		o.depends({ 'enabled': '1', 'udp_watchdog_enabled': '1' });
		o.placeholder = '223.5.5.5:53';
		o.description = _('支持格式为 <code>IP/域名:端口</code>，自动识别常见协议（53: DNS, 3478: STUN, 123: NTP）。只要有任意一个目标通畅即视为网络正常。');
		o.retain = true;

		o = s2.taboption('qos', form.DummyValue, '_live_qos_log_view', _('实时连通性监测日志'));
		o.depends({ 'enabled': '1', 'udp_watchdog_enabled': '1' });
		o.rawhtml = true;
		o.cfgvalue = function() {
			var initLiveLog = (data[3] || '');
			return '<div style="margin-top:5px;width:100%;overflow-x:auto;">' +
				'<textarea id="modem_redial_live_qos_log" class="cbi-input-textarea" cols="100" wrap="off" style="width:100%;min-width:100ch;height:310px;font-family:monospace;font-size:12px;background:#1e1e1e;color:#d4d4d4;line-height:1.45;box-sizing:border-box;white-space:pre;overflow-x:auto;resize:vertical;" readonly="readonly" placeholder="' + _('暂无实时监测数据。后台守护进程每轮检测后将自动在此覆盖刷新，也可点击下方「⚡ 立即探测一轮」...') + '">' +
				initLiveLog +
				'</textarea>' +
				'<div style="margin-top:8px;display:flex;align-items:center;flex-wrap:wrap;gap:8px;">' +
					'<button type="button" class="btn cbi-button cbi-button-action" id="btn_refresh_live_qos_log" onclick="window.refreshLiveQosLog()">🔄 ' + _('刷新实时日志') + '</button>' +
					'<button type="button" class="btn cbi-button cbi-button-apply" id="btn_run_single_probe" onclick="window.runSingleUdpProbe()">⚡ ' + _('立即探测一轮') + '</button>' +
					'<button type="button" class="btn cbi-button" id="btn_modal_test_udp" onclick="window.testCurrentUdp()">📊 ' + _('详细体检弹窗') + '</button>' +
				'</div>' +
			'</div>';
		};

		o = s2.taboption('qos', form.Value, 'udp_log_file', _('QoS 独立持久化日志路径'));
		o.depends({ 'enabled': '1', 'udp_watchdog_enabled': '1' });
		o.default = '/etc/modem_redial_qos.log';
		o.placeholder = '/etc/modem_redial_qos.log';
		o.description = _('独立记录因 UDP QoS 阻断而触发的重拨日志。保存在 <code>/etc/</code> 目录下即使路由器重启也不会丢失。');
		o.rmempty = false;
		o.retain = true;

		o = s2.taboption('qos', form.DummyValue, '_qos_log_view', _('QoS 触发重拨历史日志'));
		o.depends({ 'enabled': '1', 'udp_watchdog_enabled': '1' });
		o.rawhtml = true;
		o.cfgvalue = function() {
			var initLog = (data[2] || '');
			return '<div style="margin-top:5px;width:100%;overflow-x:auto;">' +
				'<textarea id="modem_redial_qos_log" class="cbi-input-textarea" cols="100" wrap="off" style="width:100%;min-width:100ch;height:150px;font-family:monospace;font-size:12px;background:#f8f9fa;color:#333;line-height:1.4;box-sizing:border-box;white-space:pre;overflow-x:auto;resize:vertical;" readonly="readonly" placeholder="' + _('暂无 UDP QoS 触发重拨记录 (仅在全部目标检测失败并执行重拨换 IP 时记录)...') + '">' +
				initLog +
				'</textarea>' +
				'<div style="margin-top:8px;text-align:right;">' +
					'<button type="button" class="btn cbi-button cbi-button-action" id="btn_refresh_qos_log" onclick="window.refreshQosLog()" style="margin-right:8px;">🔄 ' + _('刷新 QoS 日志') + '</button>' +
					'<button type="button" class="btn cbi-button cbi-button-reset" id="btn_clear_qos_log" onclick="window.clearQosLog()">🗑️ ' + _('清空 QoS 日志') + '</button>' +
				'</div>' +
			'</div>';
		};

		// ------------------ Tab 4: 消息推送 ------------------
		o = s2.taboption('notify', form.DummyValue, '_disabled_notify');
		o.depends('enabled', '0');
		o.rawhtml = true;
		o.cfgvalue = function() {
			return '<div style="background:rgba(0,0,0,0.02);border:1px dashed #d9d9d9;border-radius:6px;padding:24px 16px;text-align:center;margin:12px 0;">' +
				'<div style="font-size:32px;margin-bottom:8px;">⏸️</div>' +
				'<div style="font-size:16px;font-weight:600;color:#666;">' + _('插件当前处于关闭状态') + '</div>' +
				'<div style="font-size:13px;color:#999;margin-top:6px;">' + _('请先在「光猫配置」标签页中开启「启用插件」并保存应用。') + '</div>' +
			'</div>';
		};

		o = s2.taboption('notify', form.Flag, 'ntfy_enabled', _('启用 Ntfy 通知'));
		o.depends('enabled', '1');
		o.default = '0';
		o.rmempty = false;
		o.retain = true;
		o.description = _('当发生重拨换 IP、UDP QoS 阻断或任务异常时，通过 <a href="https://ntfy.sh" target="_blank" rel="noopener noreferrer">ntfy.sh</a> 或自建 ntfy 服务器向手机/桌面推送实时通知。');

		o = s2.taboption('notify', form.Value, 'ntfy_server', _('Ntfy 服务器地址'));
		o.depends({ 'enabled': '1', 'ntfy_enabled': '1' });
		o.default = 'https://ntfy.sh';
		o.placeholder = 'https://ntfy.sh';
		o.description = _('默认为官方公共服务器 <code>https://ntfy.sh</code>，若使用自建实例请填写您的完整服务器 URL。');
		o.rmempty = false;
		o.retain = true;

		o = s2.taboption('notify', form.Value, 'ntfy_topic', _('Topic 主题名称'));
		o.depends({ 'enabled': '1', 'ntfy_enabled': '1' });
		o.placeholder = 'my_modem_alerts_xxxx';
		o.description = _('ntfy 消息订阅主题（建议使用难以猜测的独特名称以防泄露，可在手机 ntfy App 中订阅此主题）。');
		o.rmempty = false;
		o.retain = true;

		o = s2.taboption('notify', form.Value, 'ntfy_token', _('访问令牌 Token (可选)'));
		o.depends({ 'enabled': '1', 'ntfy_enabled': '1' });
		o.password = true;
		o.placeholder = 'tk_... (若为公开主题可留空)';
		o.description = _('若您的主题开启了权限保护，或自建服务器要求认证，请在此填写 Bearer Access Token。');
		o.retain = true;

		o = s2.taboption('notify', form.Flag, 'notify_event_manual', _('手动重拨完成时通知'));
		o.depends({ 'enabled': '1', 'ntfy_enabled': '1' });
		o.default = '1';
		o.rmempty = false;
		o.retain = true;
		o.description = _('在 WebUI 点击「⚡ 立即重拨号换IP」或手动执行重拨成功后推送新 IP 信息。');

		o = s2.taboption('notify', form.Flag, 'notify_event_cron', _('定时自动重拨完成时通知'));
		o.depends({ 'enabled': '1', 'ntfy_enabled': '1' });
		o.default = '1';
		o.rmempty = false;
		o.retain = true;
		o.description = _('凌晨 Cron 计划任务定时重拨成功后推送新 IP 信息（若夜间不想被打扰可关闭此项）。');

		o = s2.taboption('notify', form.Flag, 'notify_event_qos', _('UDP QoS 阻断触发换 IP 时通知'));
		o.depends({ 'enabled': '1', 'ntfy_enabled': '1' });
		o.default = '1';
		o.rmempty = false;
		o.retain = true;
		o.description = _('当检测到遭遇运营商 UDP QoS 阻断并自动重新拨号换 IP 完成时推送警报与新 IP。');

		o = s2.taboption('notify', form.Flag, 'notify_event_fail', _('重拨失败告警通知'));
		o.depends({ 'enabled': '1', 'ntfy_enabled': '1' });
		o.default = '1';
		o.rmempty = false;
		o.retain = true;
		o.description = _('无论手动、定时还是 QoS 触发，当重拨过程遭遇失败（如光猫登录失败、超时未连上等）时，立即发送高优先级告警。');

		o = s2.taboption('notify', form.DummyValue, '_btn_test_ntfy_view', _('测试通知'));
		o.depends({ 'enabled': '1', 'ntfy_enabled': '1' });
		o.rawhtml = true;
		o.cfgvalue = function() {
			return '<div style="margin-top:5px;">' +
				'<button type="button" class="btn cbi-button-action" id="btn_test_ntfy" onclick="window.testNtfyNotification()">' +
					'🔔 ' + _('发送测试通知') +
				'</button>' +
				'<span id="test_ntfy_tip" style="margin-left:10px;vertical-align:middle;font-size:13px;"></span>' +
				'<div style="font-size:12px;color:#888;margin-top:6px;">' +
					_('提示：如果刚修改了服务器或 Topic，请先点击页面右下角【保存并应用】，再点击测试按钮。') +
				'</div>' +
			'</div>';
		};

		// ------------------ 日志悬浮层与轮询交互 ------------------
		window.showLogModal = function(isTriggerRedial) {
			if (window._autoCloseModalTimer) {
				clearInterval(window._autoCloseModalTimer);
				window._autoCloseModalTimer = null;
			}
			window._isRedialTriggeredManually = !!isTriggerRedial;
			if (!isTriggerRedial) {
				window._redialJustFinished = false;
			}

			var title = isTriggerRedial ? _('光猫重新拨号执行日志') : _('光猫重拨助手运行日志');

			ui.showModal(title, [
				E('div', { 'style': 'padding:5px 0;' }, [
					E('div', { 'id': 'modal_status_text', 'style': 'margin-bottom:8px;' }, [
						E('span', {
							'id': 'modal_status_badge',
							'style': isTriggerRedial ? 'color:#1890ff;font-weight:600;' : 'color:#666;'
						}, isTriggerRedial ? '⏳ ' + _('正在启动后台重拨换IP任务...') : '📜 ' + _('实时执行日志内容 (最近输出):'))
					]),
					E('div', { 'style': 'width:100%;overflow-x:auto;' }, [
						E('textarea', {
							'id': 'modem_redial_modal_log',
							'class': 'cbi-input-textarea',
							'readonly': 'readonly',
							'cols': '100',
							'wrap': 'off',
							'style': 'width:100%;min-width:100ch;height:320px;background:#1e1e1e;color:#d4d4d4;font-family:monospace;font-size:12px;line-height:1.5;padding:8px 10px;border-radius:4px;box-sizing:border-box;white-space:pre;overflow-x:auto;resize:vertical;',
							'placeholder': _('暂无执行日志...')
						})
					]),
					E('div', { 'class': 'right', 'style': 'margin-top:14px;' }, [
						E('button', {
							'class': 'btn cbi-button-reset',
							'style': 'margin-right:8px;',
							'click': function() {
								if (!confirm(_('确定清空当前日志吗？'))) return;
								fs.write('/tmp/log/modem_redial.log', '\n').then(function() {
									var box = document.getElementById('modem_redial_modal_log');
									if (box) box.value = '';
								});
							}
						}, '🗑️ ' + _('清空日志')),
						E('button', {
							'class': 'btn cbi-button-apply',
							'click': function() {
								if (window._autoCloseModalTimer) {
									clearInterval(window._autoCloseModalTimer);
									window._autoCloseModalTimer = null;
								}
								window._redialJustFinished = false;
								ui.hideModal();
							}
						}, _('关闭'))
					])
				])
			]);

			// 预先读入已有日志
			L.resolveDefault(fs.read('/tmp/log/modem_redial.log'), '').then(function(txt) {
				var box = document.getElementById('modem_redial_modal_log');
				if (box) {
					box.value = txt || '';
					box.scrollTop = box.scrollHeight;
				}
			});

			if (isTriggerRedial) {
				window.startLogPolling(true);
			}
		};

		// 全局日志轮询函数
		window.startLogPolling = function(isFromManualTrigger) {
			// 若当前正处于重拨成功后的 5 秒自动关闭倒计时中，或刚结束重拨，绝不重复拉起轮询或篡改按钮状态
			if (window._autoCloseModalTimer || window._redialJustFinished) {
				return;
			}
			if (window._modemRedialTimer) {
				return;
			}

			if (typeof isFromManualTrigger !== 'undefined') {
				window._isRedialTriggeredManually = !!isFromManualTrigger;
			}
			var pollCount = 0;
			var maxPolls = 60;

			var btn = document.getElementById('btn_manual_redial');
			if (btn) {
				btn.disabled = true;
				btn.innerText = '⏳ ' + _('正在重拨中...');
			}

			function finishPolling(isSuccess) {
				if (window._modemRedialTimer) {
					clearInterval(window._modemRedialTimer);
					window._modemRedialTimer = null;
				}

				// 标记重拨已结束，防止 status 异步回调重新触发 startLogPolling 导致按钮状态反复跳闪
				window._redialJustFinished = true;
				setTimeout(function() {
					window._redialJustFinished = false;
				}, 15000);

				var b = document.getElementById('btn_manual_redial');
				if (b) {
					b.disabled = false;
					b.innerText = '⚡ ' + _('立即重拨号换IP');
				}

				setTimeout(function() {
					window.refreshModemStatus();
				}, 800);

				var isManual = !!window._isRedialTriggeredManually;

				if (isSuccess) {
					if (isManual) {
						var countdown = 5;
						var updateCountdownBadge = function() {
							var badge = document.getElementById('modal_status_badge');
							if (badge) {
								badge.innerHTML = '<span style="color:#28a745;font-weight:600;">🎉 ' +
									_('重拨换IP成功！本窗口将在 ') + countdown + _(' 秒后自动关闭...') +
									'</span>';
							}
						};
						updateCountdownBadge();
						if (window._autoCloseModalTimer) {
							clearInterval(window._autoCloseModalTimer);
						}
						window._autoCloseModalTimer = setInterval(function() {
							if (!document.getElementById('modem_redial_modal_log')) {
								clearInterval(window._autoCloseModalTimer);
								window._autoCloseModalTimer = null;
								return;
							}
							countdown--;
							if (countdown <= 0) {
								clearInterval(window._autoCloseModalTimer);
								window._autoCloseModalTimer = null;
								window._redialJustFinished = false;
								ui.hideModal();
							} else {
								updateCountdownBadge();
							}
						}, 1000);
					} else {
						var badge = document.getElementById('modal_status_badge');
						if (badge) {
							badge.innerHTML = '<span style="color:#28a745;font-weight:600;">🎉 ' + _('重拨换IP流程成功完成！') + '</span>';
						}
					}
				} else {
					// 失败情况：绝不自动关闭悬浮层，保留完整日志供排查
					var badge = document.getElementById('modal_status_badge');
					if (badge) {
						badge.innerHTML = '<span style="color:#dc3545;font-weight:600;">❌ ' + _('重拨换IP未成功，请检查上方日志排查原因。') + '</span>';
					}
				}
			}

			window._modemRedialTimer = setInterval(function() {
				pollCount++;

				var logBox = document.getElementById('modem_redial_modal_log');

				L.resolveDefault(fs.read('/tmp/log/modem_redial.log'), '').then(function(logTxt) {
					if (logBox && logTxt) {
						logBox.value = logTxt;
						logBox.scrollTop = logBox.scrollHeight;
					}

					var isDone = false;
					var isSuccess = false;
					if (logTxt) {
						if (logTxt.indexOf('重新拨号成功') !== -1) {
							if (logTxt.indexOf('重拨换IP流程结束') !== -1 || logTxt.indexOf('释放单用户会话锁') !== -1) {
								isDone = true;
								isSuccess = true;
							}
						} else if (logTxt.indexOf('重拨换IP流程结束') !== -1 ||
							logTxt.indexOf('Traceback') !== -1 ||
							logTxt.indexOf('已有重拨任务在运行中') !== -1 ||
							logTxt.indexOf('处于关闭禁用状态') !== -1 ||
							logTxt.indexOf('未配置') !== -1) {
							isDone = true;
							isSuccess = false;
						}
					}

					// 辅助检查进程状态 (每2秒检查一次)
					if (!isDone && pollCount % 2 === 0 && pollCount >= 4) {
						L.resolveDefault(fs.exec('/usr/bin/modem_redial', ['--status']), {}).then(function(res) {
							try {
								var raw = (res && res.stdout) ? res.stdout : res;
								var s = JSON.parse(raw || '{}');
								if (s.running === false) {
									var success = (logTxt && logTxt.indexOf('重新拨号成功') !== -1);
									clearInterval(window._modemRedialTimer);
									window._modemRedialTimer = null;
									finishPolling(success);
									return;
								}
							} catch(e) {}
						});
					}

					if (isDone || pollCount >= maxPolls) {
						clearInterval(window._modemRedialTimer);
						window._modemRedialTimer = null;
						finishPolling(isSuccess);
						return;
					}
				}).catch(function(err) {
					if (pollCount >= maxPolls) {
						clearInterval(window._modemRedialTimer);
						window._modemRedialTimer = null;
						finishPolling(false);
					}
				});
			}, 1000);
		};

		// 挂载全局交互脚本
		window.triggerModemRedial = function() {
			if (!confirm('确定立即触发光猫重新拨号换IP吗？拨号期间宽带会短暂中断 3~5 秒。')) return;

			window._redialJustFinished = false;
			if (window._autoCloseModalTimer) {
				clearInterval(window._autoCloseModalTimer);
				window._autoCloseModalTimer = null;
			}
			if (window._modemRedialTimer) {
				clearInterval(window._modemRedialTimer);
				window._modemRedialTimer = null;
			}

			var btn = document.getElementById('btn_manual_redial');
			if (btn) {
				btn.disabled = true;
				btn.innerText = '⏳ ' + _('正在启动任务...');
			}

			// 预先写入初始日志行，覆盖上一轮的成功结束标志，并立即打开悬浮日志层
			fs.write('/tmp/log/modem_redial.log', '[*] 正在启动后台守护重拨换IP任务...\n').then(function() {
				window.showLogModal(true);

				fs.exec('/usr/bin/modem_redial', ['--start']).then(function(res) {
					var stdout = (res && res.stdout) ? res.stdout.trim() : '';
					if (stdout.indexOf('PLUGIN_DISABLED') !== -1) {
						if (window._modemRedialTimer) {
							clearInterval(window._modemRedialTimer);
							window._modemRedialTimer = null;
						}
						if (btn) { btn.disabled = false; btn.innerText = '⚡ ' + _('立即重拨号换IP'); }
						var badge = document.getElementById('modal_status_badge');
						if (badge) {
							badge.innerHTML = '<span style="color:#dc3545;font-weight:600;">❌ ' + _('插件当前处于未生效状态，请先在「光猫配置」中开启并保存应用！') + '</span>';
						} else {
							ui.addNotification(null, E('p', _('插件当前处于未生效状态，请先在「光猫配置」中开启并保存应用！')));
						}
						return;
					}
					if (stdout.indexOf('NOT_CONFIGURED') !== -1) {
						if (window._modemRedialTimer) {
							clearInterval(window._modemRedialTimer);
							window._modemRedialTimer = null;
						}
						if (btn) { btn.disabled = false; btn.innerText = '⚡ ' + _('立即重拨号换IP'); }
						var badge = document.getElementById('modal_status_badge');
						if (badge) {
							badge.innerHTML = '<span style="color:#dc3545;font-weight:600;">❌ ' + _('光猫后台地址、用户名或密码未配置，请先保存配置！') + '</span>';
						} else {
							ui.addNotification(null, E('p', _('光猫后台地址、用户名或密码未配置，请先保存配置！')));
						}
						return;
					}
					if (stdout.indexOf('ALREADY_RUNNING') !== -1) {
						var badge = document.getElementById('modal_status_badge');
						if (badge) {
							badge.innerHTML = '<span style="color:#ffc107;font-weight:600;">⚠️ ' + _('已有重拨换IP任务正在后台运行中，正在同步回显日志...') + '</span>';
						}
						return;
					}
				}).catch(function(err) {
					// 容错处理：光猫重拨断网瞬间可能伴随短暂网络瞬断，先校验是否已在后台平稳运行
					L.resolveDefault(fs.read('/tmp/log/modem_redial.log'), '').then(function(logTxt) {
						if (logTxt && (logTxt.indexOf('正在') !== -1 || logTxt.indexOf('步骤') !== -1 || logTxt.indexOf('切换') !== -1 || logTxt.indexOf('探测') !== -1 || logTxt.indexOf('重拨') !== -1)) {
							// 守护任务已在平稳推进中，不中断轮询
							return;
						}
						if (window._modemRedialTimer) {
							clearInterval(window._modemRedialTimer);
							window._modemRedialTimer = null;
						}
						if (btn) {
							btn.disabled = false;
							btn.innerText = '⚡ ' + _('立即重拨号换IP');
						}
						var badge = document.getElementById('modal_status_badge');
						if (badge) {
							badge.innerHTML = '<span style="color:#dc3545;font-weight:600;">❌ ' + _('启动重拨任务失败: ') + (err.message || err) + '</span>';
						}
					});
				});
			});
		};

		window.refreshModemStatus = function(isManualClick) {
			var btn = document.getElementById('btn_refresh_status');
			var ipEl = document.getElementById('modem_current_ip');
			var statusEl = document.getElementById('modem_conn_status');
			var triggerEl = document.getElementById('modem_trigger_mode');

			if (isManualClick) {
				if (btn) {
					btn.disabled = true;
					btn.innerText = '⏳ ' + _('正在刷新...');
				}
				if (ipEl) {
					ipEl.innerHTML = '<span style="color:#888;font-size:14px;font-weight:normal;">⏳ ' + _('正在读取...') + '</span>';
				}
				if (statusEl) {
					statusEl.innerHTML = '<span style="color:#888;font-size:14px;font-weight:normal;">⏳ ' + _('正在检测...') + '</span>';
				}
				if (triggerEl) {
					triggerEl.innerHTML = '<span style="color:#888;font-size:14px;font-weight:normal;">⏳ ' + _('正在查询...') + '</span>';
				}
			}

			var statusParams = isManualClick ? ['--status', '--force'] : ['--status'];
			fs.exec('/usr/bin/modem_redial', statusParams).then(function(res) {
				try {
					var raw = (res && res.stdout) ? res.stdout : res;
					var data = JSON.parse(raw || '{}');
					if (ipEl) ipEl.innerText = data.ip || '未知';
					if (statusEl) {
						statusEl.innerText = data.status || '未知';
						statusEl.style.color = (data.status === 'Connected' || data.status === '已连接') ? '#28a745' : ((data.status === 'Disconnected' || data.status === '未连接') ? '#dc3545' : (data.status === '未配置' || data.status === '未启用' ? '#6c757d' : '#ffc107'));
					}
					if (triggerEl) triggerEl.innerText = data.trigger || '-';

					// 严格检查：当且仅当非刚完成重拨且无活动倒计时/轮询时，才跟随 running 开启轮询
					if (data.running && !window._autoCloseModalTimer && !window._redialJustFinished && !window._modemRedialTimer) {
						window.startLogPolling();
					}

					if (isManualClick && btn) {
						btn.innerText = '✅ ' + _('已刷新');
						setTimeout(function() {
							btn.disabled = false;
							btn.innerText = '🔄 ' + _('刷新状态');
						}, 700);
					}
				} catch(e) {
					if (isManualClick && btn) {
						btn.disabled = false;
						btn.innerText = '🔄 ' + _('刷新状态');
					}
				}
			}).catch(function(err) {
				if (isManualClick && btn) {
					btn.innerText = '❌ ' + _('刷新失败');
					setTimeout(function() {
						btn.disabled = false;
						btn.innerText = '🔄 ' + _('刷新状态');
					}, 1000);
				}
			});
		};

		// 检查 GitHub 最新版本 (完全异步非阻塞，支持内存级高速缓存)
		window.checkPluginUpdate = function(isAuto) {
			var btn = document.getElementById('btn_check_update');
			var tip = document.getElementById('check_update_tip');
			if (!isAuto) {
				if (tip) tip.innerHTML = '';
				if (btn) {
					btn.disabled = true;
					btn.innerText = '⏳ ' + _('正在检查最新版本...');
				}
			}

			// 若为静默自动检测，先尝试读取本地 30 分钟缓存，0 毫秒即时响应，绝不产生网络阻塞
			var checkPromise;
			if (isAuto) {
				checkPromise = L.resolveDefault(fs.read('/tmp/log/modem_redial_update_cache.json'), '').then(function(raw) {
					try {
						var cached = JSON.parse((raw || '').trim());
						if (cached && cached.success) {
							return { stdout: raw };
						}
					} catch(e) {}
					return fs.exec('/usr/bin/modem_redial', ['--check-update']);
				});
			} else {
				checkPromise = fs.exec('/usr/bin/modem_redial', ['--check-update', '--force']);
			}

			checkPromise.then(function(res) {
				if (!isAuto && btn) {
					btn.disabled = false;
					btn.innerText = '🚀 ' + _('检查更新');
				}

				var raw = (res && res.stdout) ? res.stdout.trim() : '';
				var info = {};
				try {
					info = JSON.parse(raw || '{}');
				} catch(e) {
					if (!isAuto) {
						if (tip) {
							tip.innerHTML = '<span style="color:#ff4d4f;font-size:12px;">❌ ' + _('解析更新信息失败') + '</span>';
						} else {
							ui.addNotification(null, E('p', _('解析更新信息失败: ') + raw));
						}
					}
					return;
				}

				if (!info.success) {
					if (!isAuto) {
						if (tip) {
							tip.innerHTML = '<span style="color:#ff4d4f;font-size:12px;">❌ ' + (info.error || _('检查更新失败')) + '</span>';
						} else {
							ui.addNotification(null, E('p', _('检查更新失败: ') + (info.error || _('无法连接 GitHub'))));
						}
					}
					return;
				}

				if (!info.has_update) {
					if (!isAuto && tip) {
						tip.innerHTML = '<span style="color:#2da44e;font-size:13px;font-weight:600;">✅ ' + _('已经是最新版') + '</span>';
					}
					return;
				}

				// 发现新版本！
				if (tip) {
					tip.innerHTML = '<span style="color:#1890ff;font-size:12px;font-weight:600;">✨ 发现新版本 ' + info.latest_version + '</span>';
				}

				// 若当前已有日志模态层展示（如正在重拨或看日志），不强制覆盖阻断用户
				if (document.getElementById('modem_redial_modal_log')) {
					return;
				}

				// 自动弹出更新悬浮层
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
				if (!isAuto) {
					if (btn) {
						btn.disabled = false;
						btn.innerText = '🚀 ' + _('检查更新');
					}
					if (tip) {
						tip.innerHTML = '<span style="color:#ff4d4f;font-size:12px;">❌ ' + _('检查失败: ') + (err.message || err) + '</span>';
					} else {
						ui.addNotification(null, E('p', _('请求检查更新出错: ') + (err.message || err)));
					}
				}
			});
		};

		// 测试当前 UDP 连通性
		window.testCurrentUdp = function() {
			ui.showModal(_('正在测试 UDP 连通性'), [
				E('div', { 'style': 'text-align:center;padding:25px 15px;' }, [
					E('div', { 'style': 'font-size:36px;margin-bottom:12px;' }, '📡'),
					E('p', { 'style': 'font-size:15px;font-weight:600;' }, _('正在向配置的目标节点发送双向 UDP 探测包...')),
					E('p', { 'style': 'font-size:12px;color:#888;margin-top:6px;' }, _('测试涵盖 DNS (53)、STUN (3478) 与 NTP (123) 协议，请稍候...'))
				])
			]);

			fs.exec('/usr/bin/modem_redial', ['--test-udp']).then(function(res) {
				var raw = (res && res.stdout) ? res.stdout.trim() : '';
				var data = {};
				try {
					data = JSON.parse(raw || '{}');
				} catch(e) {
					data = { all_failed: true, error: raw };
				}

				if (data.error && (!data.results || data.results.length === 0)) {
					ui.showModal(_('测试提示'), [
						E('div', { 'style': 'padding:15px 5px;' }, [
							E('p', { 'style': 'color:#dc3545;font-size:14px;' }, '⚠️ ' + data.error),
							E('div', { 'class': 'right', 'style': 'margin-top:15px;' }, [
								E('button', { 'class': 'btn', 'click': ui.hideModal }, _('关闭'))
							])
						])
					]);
					return;
				}

				var results = data.results || [];
				var rows = [];

				for (var i = 0; i < results.length; i++) {
					var item = results[i];
					var statusBadge = item.ok
						? E('span', { 'style': 'color:#28a745;font-weight:600;' }, '✅ ' + _('正常') + ' (' + item.rtt + 'ms)')
						: E('span', { 'style': 'color:#dc3545;font-weight:600;' }, '❌ ' + _('不通') + ' (' + (item.msg || _('超时')) + ')');

					rows.push(E('tr', {}, [
						E('td', { 'style': 'font-weight:bold;' }, item.target),
						E('td', {}, E('span', { 'class': 'badge' }, item.proto || 'UDP')),
						E('td', {}, statusBadge)
					]));
				}

				var summaryText = '';
				var summaryColor = '';
				if (data.all_failed) {
					summaryText = _('⚠️ 全部 UDP 目标均不可达！当前网络极可能遭遇运营商 UDP QoS 限制或断流！');
					summaryColor = '#dc3545';
				} else {
					summaryText = _('🎉 UDP 连通性正常！已收到目标节点的回包响应。');
					summaryColor = '#28a745';
				}

				ui.showModal(_('UDP 连通性测试结果'), [
					E('div', { 'style': 'padding:15px 5px;' }, [
						E('p', { 'style': 'font-size:15px;font-weight:600;color:' + summaryColor + ';margin-bottom:12px;' }, summaryText),
						E('table', { 'class': 'table', 'style': 'width:100%;font-size:13px;' }, [
							E('thead', {}, [
								E('tr', {}, [
									E('th', {}, _('目标服务器')),
									E('th', {}, _('协议')),
									E('th', {}, _('测试结果'))
								])
							]),
							E('tbody', {}, rows)
						]),
						E('div', { 'class': 'right', 'style': 'margin-top:18px;' }, [
							E('button', { 'class': 'btn', 'click': ui.hideModal }, _('关闭'))
						])
					])
				]);

				// 同步更新实时监测日志显示框
				L.resolveDefault(fs.read('/tmp/log/modem_redial_live_qos.log'), '').then(function(txt) {
					var liveBox = document.getElementById('modem_redial_live_qos_log');
					if (liveBox && txt) liveBox.value = txt;
				});
			}).catch(function(err) {
				ui.showModal(_('测试发生异常'), [
					E('div', { 'style': 'padding:15px 5px;' }, [
						E('p', { 'style': 'color:#dc3545;font-size:14px;' }, '❌ ' + (err.message || err)),
						E('div', { 'class': 'right', 'style': 'margin-top:15px;' }, [
							E('button', { 'class': 'btn', 'click': ui.hideModal }, _('关闭'))
						])
					])
				]);
			});
		};

		// 执行一键升级 (采用 v1.5.0 经典直连高速升级机制，2~3 秒极速完成)
		window.doPluginUpdate = function(downloadUrl, newVersion) {
			ui.showModal(_('正在升级插件'), [
				E('div', { 'style': 'text-align:center;padding:25px 15px;' }, [
					E('div', { 'style': 'font-size:36px;margin-bottom:12px;' }, '⏳'),
					E('p', { 'style': 'font-size:16px;font-weight:600;' }, [
						_('正在下载并安装最新版本 ') + (newVersion || '') + ' ...'
					]),
					E('p', { 'style': 'font-size:12px;color:#888;margin-top:6px;' }, _('正在下载最新 IPK 安装包并执行覆盖安装，整个过程约需 2~3 秒，请稍候...'))
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
							E('div', { 'style': 'font-size:36px;margin-bottom:12px;' }, '🎉'),
							E('p', { 'style': 'font-size:16px;font-weight:600;color:#28a745;' }, _('插件已成功升级至最新版本！')),
							E('p', { 'style': 'font-size:13px;color:#666;margin-top:8px;' }, _('系统已恢复您的全部配置，页面将在 2.5 秒后自动刷新...'))
						])
					]);
					setTimeout(function() {
						location.reload();
					}, 2500);
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

		// 刷新实时监测日志 (内存临时日志)
		window.refreshLiveQosLog = function() {
			var liveBox = document.getElementById('modem_redial_live_qos_log');
			var btn = document.getElementById('btn_refresh_live_qos_log');
			if (btn) {
				btn.disabled = true;
				btn.innerText = '⏳ ' + _('读取中...');
			}
			fs.exec('/usr/bin/modem_redial', ['--show-live-qos-log']).then(function(res) {
				var txt = (res && res.stdout) ? res.stdout.trim() : '';
				if (liveBox && txt) {
					liveBox.value = txt;
				}
				if (btn) {
					btn.innerText = '✅ ' + _('已刷新');
					setTimeout(function() {
						btn.disabled = false;
						btn.innerText = '🔄 ' + _('刷新实时日志');
					}, 800);
				}
			}).catch(function() {
				if (btn) {
					btn.disabled = false;
					btn.innerText = '🔄 ' + _('刷新实时日志');
				}
			});
		};

		// 立即探测一轮 UDP 并同步展示最新单轮结果
		window.runSingleUdpProbe = function() {
			if (window._isProbingUdp) return;
			window._isProbingUdp = true;

			var btn = document.getElementById('btn_run_single_probe');
			var liveBox = document.getElementById('modem_redial_live_qos_log');

			if (btn) {
				btn.disabled = true;
				btn.innerText = '⏳ ' + _('正在探测...');
			}
			if (liveBox) {
				liveBox.value = '>>> ' + _('正在向所有目标节点发送 UDP 探测包，请稍候...') + '\n' + (liveBox.value || '');
			}

			fs.exec('/usr/bin/modem_redial', ['--test-udp']).then(function(res) {
				window._isProbingUdp = false;
				if (btn) {
					btn.innerText = '✅ ' + _('探测完成');
					setTimeout(function() {
						btn.disabled = false;
						btn.innerText = '⚡ ' + _('立即探测一轮');
					}, 1200);
				}
				var raw = (res && res.stdout) ? res.stdout.trim() : '';
				var data = {};
				try {
					data = JSON.parse(raw || '{}');
				} catch(e) {}

				if (liveBox) {
					if (data.log_text) {
						liveBox.value = data.log_text;
					} else {
						// 备用方式：通过 --show-live-qos-log 命令直接读取
						fs.exec('/usr/bin/modem_redial', ['--show-live-qos-log']).then(function(sRes) {
							var sTxt = (sRes && sRes.stdout) ? sRes.stdout.trim() : '';
							if (sTxt) {
								liveBox.value = sTxt;
							} else if (raw) {
								liveBox.value = raw;
							}
						}).catch(function() {
							if (raw) liveBox.value = raw;
						});
					}
				}
			}).catch(function(err) {
				window._isProbingUdp = false;
				if (btn) {
					btn.disabled = false;
					btn.innerText = '⚡ ' + _('立即探测一轮');
				}
				if (liveBox) {
					liveBox.value = '❌ ' + _('探测执行失败: ') + (err.message || err);
				}
			});
		};

		// 刷新与清空 QoS 历史日志
		window.refreshQosLog = function() {
			var qosBox = document.getElementById('modem_redial_qos_log');
			if (!qosBox) return;
			fs.exec('/usr/bin/modem_redial', ['--show-qos-log']).then(function(res) {
				var txt = (res && typeof res.stdout === 'string') ? res.stdout : '';
				qosBox.value = txt;
				qosBox.scrollTop = qosBox.scrollHeight;
			}).catch(function() {
				L.resolveDefault(fs.read('/etc/modem_redial_qos.log'), '').then(function(txt) {
					qosBox.value = txt || '';
					qosBox.scrollTop = qosBox.scrollHeight;
				});
			});
		};

		window.clearQosLog = function() {
			if (!confirm('确定要清空 UDP QoS 触发重拨历史日志吗？')) return;
			fs.exec('/usr/bin/modem_redial', ['--clear-qos-log']).then(function() {
				var qosBox = document.getElementById('modem_redial_qos_log');
				if (qosBox) qosBox.value = '';
			});
		};

		// 测试 Ntfy 消息通知
		window.testNtfyNotification = function() {
			if (window._isTestingNtfy) return;
			window._isTestingNtfy = true;

			var btn = document.getElementById('btn_test_ntfy');
			var tip = document.getElementById('test_ntfy_tip');
			if (btn) {
				btn.disabled = true;
				btn.innerText = '⏳ ' + _('正在发送测试通知...');
			}
			if (tip) tip.innerHTML = '';

			fs.exec('/usr/bin/modem_redial', ['--test-ntfy']).then(function(res) {
				window._isTestingNtfy = false;
				if (btn) {
					btn.disabled = false;
					btn.innerText = '🔔 ' + _('发送测试通知');
				}
				var raw = (res && res.stdout) ? res.stdout.trim() : '';
				var info = {};
				try {
					info = JSON.parse(raw || '{}');
				} catch(e) {
					if (tip) tip.innerHTML = '<span style="color:#ff4d4f;">❌ ' + _('解析测试结果失败: ') + raw + '</span>';
					return;
				}

				if (info.success) {
					if (tip) tip.innerHTML = '<span style="color:#2da44e;font-weight:600;">✅ ' + _('测试通知已发送，请检查您的手机或终端设备！') + '</span>';
				} else {
					if (tip) tip.innerHTML = '<span style="color:#ff4d4f;font-weight:600;">❌ ' + _('发送失败: ') + (info.error || '未知错误') + '</span>';
				}
			}).catch(function(err) {
				window._isTestingNtfy = false;
				if (btn) {
					btn.disabled = false;
					btn.innerText = '🔔 ' + _('发送测试通知');
				}
				if (tip) tip.innerHTML = '<span style="color:#ff4d4f;">❌ ' + _('请求出错: ') + (err.message || err) + '</span>';
			});
		};

		// 若页面初始化加载时检测到已有重拨任务在运行，自动弹出悬浮层展示进度
		try {
			var rawInit = (data[1] && data[1].stdout) ? data[1].stdout : data[1];
			var initialStatus = JSON.parse(rawInit || '{}');
			if (initialStatus.running) {
				setTimeout(function() {
					window.showLogModal(true);
				}, 600);
			}
		} catch(e) {}

		// 每次进入插件，延时 3.5 秒后在后台完全异步静默检测更新，绝不阻塞首次页面渲染与交互
		setTimeout(function() {
			window.checkPluginUpdate(true);
		}, 3500);

		// 保底启动 UDP 连通性监测守护进程 (若已启用但未在运行，秒级拉起)
		fs.exec('/usr/bin/modem_redial', ['--start-watchdog']);

		// 周期性轮询刷新 UDP 实时监测日志 (后台静默读取最新单轮日志，避开聚焦选中文本状态)
		setInterval(function() {
			var liveBox = document.getElementById('modem_redial_live_qos_log');
			if (!liveBox || liveBox.offsetParent === null) return;
			if (liveBox.matches && liveBox.matches(':focus')) return;
			fs.exec('/usr/bin/modem_redial', ['--show-live-qos-log']).then(function(res) {
				var txt = (res && res.stdout) ? res.stdout.trim() : '';
				if (liveBox && txt && liveBox.value !== txt) {
					liveBox.value = txt;
				}
			});
		}, 3000);

		return m.render();
	}
});
