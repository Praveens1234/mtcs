import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:mtcs_mobile/providers/engine_provider.dart';
import 'package:mtcs_mobile/providers/trading_provider.dart';
import 'package:mtcs_mobile/widgets/shared_widgets.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({Key? key}) : super(key: key);

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Provider.of<EngineProvider>(context, listen: false).connectSse();
      Provider.of<TradingProvider>(context, listen: false).startPollingPositions();
    });
  }

  @override
  void dispose() {
    Provider.of<TradingProvider>(context, listen: false).stopPollingPositions();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('MTCS Dashboard'),
      ),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: () async {
            Provider.of<TradingProvider>(context, listen: false).fetchPositions();
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
    );
  }

  Widget _buildSystemStatusCard(BuildContext context) {
    return Consumer<EngineProvider>(
      builder: (context, engine, child) {
        final isRunning = engine.status == "COPYING ACTIVE" || engine.status == "ACTIVE" || engine.status == "RUNNING";
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
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        Container(
                          width: 10,
                          height: 10,
                          decoration: BoxDecoration(
                            color: isRunning ? Colors.greenAccent : Colors.redAccent,
                            shape: BoxShape.circle,
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          engine.status,
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
                      await engine.toggleEngine(!isRunning);
                      ScaffoldMessenger.of(context).showSnackBar(
                        SnackBar(content: Text('Engine command sent')),
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
    return Consumer<EngineProvider>(
      builder: (context, engine, child) {
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
                  child: MetricCard(
                    title: "Total Equity",
                    value: "\$${engine.masterEquity.toStringAsFixed(2)}",
                    icon: Icons.account_balance_wallet_outlined,
                    color: Colors.blue,
                  ),
                ),
                const SizedBox(width: 16),
                Expanded(
                  child: MetricCard(
                    title: "Floating P/L",
                    value: "\$${engine.masterProfit.toStringAsFixed(2)}",
                    icon: Icons.show_chart,
                    color: engine.masterProfit >= 0 ? Colors.green : Colors.red,
                  ),
                ),
              ],
            )
          ],
        );
      },
    );
  }

  Widget _buildActivePositions(BuildContext context) {
    return Consumer<TradingProvider>(
      builder: (context, trading, child) {
        final positions = trading.positions;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  "Active Positions (${positions.length})",
                  style: Theme.of(context).textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
                if (positions.isNotEmpty)
                  TextButton(
                    onPressed: () {
                      for (var p in positions) {
                        trading.closePosition(p.ticket);
                      }
                    },
                    child: const Text("Close All", style: TextStyle(color: Colors.red)),
                  ),
              ],
            ),
            const SizedBox(height: 8),
            if (positions.isEmpty)
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
              )
            else
              ListView.builder(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                itemCount: positions.length,
                itemBuilder: (context, index) {
                  final p = positions[index];
                  final isBuy = p.type == 0;
                  return Card(
                    margin: const EdgeInsets.only(bottom: 8),
                    child: ListTile(
                      leading: StatusBadge(status: isBuy ? 'BUY' : 'SELL', isGood: isBuy),
                      title: Text("${p.symbol}  ${p.volume} lots"),
                      subtitle: Text("Open: ${p.priceOpen} | Current: ${p.currentPrice}"),
                      trailing: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            "\$${p.profit.toStringAsFixed(2)}",
                            style: TextStyle(
                              color: p.profit >= 0 ? Colors.green : Colors.red,
                              fontWeight: FontWeight.bold,
                              fontSize: 16,
                            ),
                          ),
                          IconButton(
                            icon: const Icon(Icons.close, color: Colors.grey),
                            onPressed: () => trading.closePosition(p.ticket),
                          )
                        ],
                      ),
                    ),
                  );
                },
              ),
          ],
        );
      }
    );
  }
}
