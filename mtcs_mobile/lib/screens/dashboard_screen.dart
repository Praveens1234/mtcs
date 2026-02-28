import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:mtcs_mobile/providers/system_state_provider.dart';
import 'package:mtcs_mobile/api/api_service.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({Key? key}) : super(key: key);

  @override
  _DashboardScreenState createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  String _totalEquity = "\$0.00";
  String _floatingPl = "\$0.00";

  @override
  void initState() {
    super.initState();
    _connectSse();
  }

  void _connectSse() {
    try {
      ApiService.getSseStream('/api/sse/stream').listen((event) {
        if (event.id == '' && event.event == '' && event.data == '') return;

        try {
          final data = json.decode(event.data ?? '{}');
          if (mounted) {
            setState(() {
              if (data['metrics'] != null && data['metrics']['master'] != null) {
                final master = data['metrics']['master'];
                _totalEquity = "\$${master['equity'] ?? '0.00'}";
                _floatingPl = "\$${master['profit'] ?? '0.00'}";
              }
            });
            Provider.of<SystemStateProvider>(context, listen: false)
                .updateState(data['engine_status'] ?? 'UNKNOWN', DateTime.now().toIso8601String());
          }
        } catch (e) {
          debugPrint("JSON Parse error: $e");
        }
      });
    } catch (e) {
      debugPrint("SSE connect error: $e");
    }
  }

  @override
  void dispose() {
    ApiService.unsubscribeSse();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('MTCS Engine'),
        actions: [
          IconButton(
            icon: const Icon(Icons.notifications_outlined),
            onPressed: () {},
          )
        ],
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () async {
            // refresh data
            await Future.delayed(const Duration(seconds: 1));
          },
          child: SingleChildScrollView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: const EdgeInsets.all(16.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _buildSystemStatusCard(context),
                const SizedBox(height: 24),
                _buildEquityOverview(context),
                const SizedBox(height: 24),
                _buildActivePositions(context),
              ],
            ),
          ),
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () {
          // Open quick trade
        },
        icon: const Icon(Icons.flash_on),
        label: const Text("Trade"),
      ),
    );
  }

  Widget _buildSystemStatusCard(BuildContext context) {
    return Consumer<SystemStateProvider>(
      builder: (context, systemState, child) {
        final isRunning = systemState.status != "DISCONNECTED" && systemState.status != "STOPPED";
        return Card(
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(16),
            side: BorderSide(
              color: Theme.of(context).colorScheme.outline.withOpacity(0.2),
            ),
          ),
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      "System Engine",
                      style: Theme.of(context).textTheme.titleSmall?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Row(
                      children: [
                        Container(
                          width: 8,
                          height: 8,
                          decoration: BoxDecoration(
                            color: isRunning ? Colors.greenAccent : Colors.redAccent,
                            shape: BoxShape.circle,
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          systemState.status,
                          style: Theme.of(context).textTheme.titleMedium?.copyWith(
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
                FilledButton.icon(
                  onPressed: () async {
                    try {
                      final action = isRunning ? 'stop' : 'start';
                      await ApiService.post('/api/system/engine', {'action': action});
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(content: Text('Engine $action command sent')),
                      );
                    } catch (e) {
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(content: Text('Error: $e'), backgroundColor: Colors.red),
                      );
                    }
                  },
                  icon: Icon(isRunning ? Icons.stop : Icons.power_settings_new),
                  label: Text(isRunning ? "Stop Engine" : "Start Engine"),
                  style: FilledButton.styleFrom(
                    backgroundColor: isRunning ? Colors.red : Theme.of(context).colorScheme.primary,
                    foregroundColor: Colors.white,
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildEquityOverview(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          "Equity Overview",
          style: Theme.of(context).textTheme.titleLarge?.copyWith(
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 16),
        Row(
          children: [
            Expanded(
              child: _buildMetricCard(context, "Total Equity", _totalEquity, Icons.account_balance_wallet_outlined, Colors.blue),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: _buildMetricCard(context, "Floating P/L", _floatingPl, Icons.show_chart, _floatingPl.startsWith('-\$') ? Colors.red : Colors.green),
            ),
          ],
        )
      ],
    );
  }

  Widget _buildMetricCard(BuildContext context, String title, String value, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Theme.of(context).cardColor,
        borderRadius: BorderRadius.circular(16),
        border: BorderSide(color: Theme.of(context).colorScheme.outline.withOpacity(0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 20, color: color),
              const SizedBox(width: 8),
              Text(
                title,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            value,
            style: Theme.of(context).textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActivePositions(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
              "Active Positions",
              style: Theme.of(context).textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            TextButton(
              onPressed: () {},
              child: const Text("Close All"),
            ),
          ],
        ),
        const SizedBox(height: 8),
        Center(
          child: Padding(
            padding: const EdgeInsets.all(32.0),
            child: Column(
              children: [
                Icon(Icons.inbox_outlined, size: 48, color: Theme.of(context).colorScheme.onSurfaceVariant),
                const SizedBox(height: 16),
                Text(
                  "No active positions",
                  style: Theme.of(context).textTheme.bodyLarge?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }
}
