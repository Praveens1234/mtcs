import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:webview_flutter/webview_flutter.dart';

void main() {
  runApp(const MtcsMobileApp());
}

class MtcsMobileApp extends StatelessWidget {
  const MtcsMobileApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'MTCS Mobile',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF0B1020),
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF42A5F5),
          brightness: Brightness.dark,
        ),
      ),
      home: const TradingWebShell(),
    );
  }
}

class TradingWebShell extends StatefulWidget {
  const TradingWebShell({super.key});

  @override
  State<TradingWebShell> createState() => _TradingWebShellState();
}

class _TradingWebShellState extends State<TradingWebShell> {
  static const _serverKey = 'mtcs_server_url';
  static const _defaultServer = 'http://192.168.1.100:9600';

  final TextEditingController _serverController = TextEditingController();

  WebViewController? _webViewController;
  double _progress = 0;
  String _activeServer = _defaultServer;
  String? _errorText;

  @override
  void initState() {
    super.initState();
    _loadSavedServer();
  }

  @override
  void dispose() {
    _serverController.dispose();
    super.dispose();
  }

  Future<void> _loadSavedServer() async {
    final prefs = await SharedPreferences.getInstance();
    final saved = prefs.getString(_serverKey);
    final server = (saved == null || saved.isEmpty) ? _defaultServer : saved;

    if (!mounted) {
      return;
    }

    setState(() {
      _activeServer = server;
      _serverController.text = server;
      _initializeWebView(server);
    });
  }

  void _initializeWebView(String serverUrl) {
    final controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setNavigationDelegate(
        NavigationDelegate(
          onProgress: (progress) {
            if (!mounted) {
              return;
            }
            setState(() {
              _progress = progress / 100;
              _errorText = null;
            });
          },
          onWebResourceError: (error) {
            if (!mounted) {
              return;
            }
            setState(() {
              _errorText = 'Cannot reach MTCS server at $_activeServer. '
                  'Verify both devices are in the same network and server is running.';
            });
          },
        ),
      )
      ..loadRequest(Uri.parse(serverUrl));

    _webViewController = controller;
  }

  Future<void> _saveAndReloadServer() async {
    final normalized = _normalizeUrl(_serverController.text);
    if (normalized == null) {
      setState(() {
        _errorText = 'Enter a valid server URL like http://192.168.1.100:9600';
      });
      return;
    }

    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_serverKey, normalized);

    if (!mounted) {
      return;
    }

    setState(() {
      _activeServer = normalized;
      _errorText = null;
      _initializeWebView(normalized);
    });
  }

  String? _normalizeUrl(String raw) {
    var text = raw.trim();
    if (text.isEmpty) {
      return null;
    }

    if (!text.startsWith('http://') && !text.startsWith('https://')) {
      text = 'http://$text';
    }

    final uri = Uri.tryParse(text);
    if (uri == null || uri.host.isEmpty) {
      return null;
    }

    return uri.toString();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('MTCS Mobile Console'),
        flexibleSpace: Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              colors: [Color(0xFF142850), Color(0xFF0F4C75)],
            ),
          ),
        ),
        actions: [
          IconButton(
            tooltip: 'Configure server',
            onPressed: _showServerSheet,
            icon: const Icon(Icons.settings_rounded),
          ),
          IconButton(
            tooltip: 'Refresh',
            onPressed: () => _webViewController?.reload(),
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: Column(
        children: [
          if (_progress < 1)
            LinearProgressIndicator(
              value: _progress,
              minHeight: 3,
            ),
          Material(
            color: const Color(0xFF0F172A),
            child: ListTile(
              dense: true,
              leading: const Icon(Icons.wifi_tethering_rounded, size: 20),
              title: Text(
                _activeServer,
                style: const TextStyle(fontSize: 12.5),
                overflow: TextOverflow.ellipsis,
              ),
              subtitle: const Text('Connected over local network'),
            ),
          ),
          if (_errorText != null)
            Padding(
              padding: const EdgeInsets.all(12),
              child: Card(
                color: Colors.red.withValues(alpha: 0.2),
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Text(_errorText!),
                ),
              ),
            ),
          Expanded(
            child: _webViewController == null
                ? const Center(child: CircularProgressIndicator())
                : ClipRRect(
                    borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
                    child: WebViewWidget(controller: _webViewController!),
                  ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showServerSheet,
        icon: const Icon(Icons.router_rounded),
        label: const Text('Server'),
      ),
    );
  }

  void _showServerSheet() {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: const Color(0xFF111827),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (_) {
        return Padding(
          padding: EdgeInsets.only(
            left: 16,
            right: 16,
            top: 20,
            bottom: MediaQuery.of(context).viewInsets.bottom + 24,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'MTCS Server Endpoint',
                style: TextStyle(fontSize: 20, fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 8),
              const Text(
                'Use your machine LAN IP so this APK can access the MTCS server on your network.',
                style: TextStyle(color: Colors.white70),
              ),
              const SizedBox(height: 16),
              TextField(
                controller: _serverController,
                keyboardType: TextInputType.url,
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  labelText: 'Server URL',
                  hintText: 'http://192.168.1.100:9600',
                ),
              ),
              const SizedBox(height: 16),
              SizedBox(
                width: double.infinity,
                child: FilledButton.icon(
                  onPressed: () async {
                    await _saveAndReloadServer();
                    if (mounted) {
                      Navigator.of(context).pop();
                    }
                  },
                  icon: const Icon(Icons.check_circle_rounded),
                  label: const Text('Save & Connect'),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
