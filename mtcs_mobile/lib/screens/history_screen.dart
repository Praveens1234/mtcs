import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:mtcs_mobile/providers/trading_provider.dart';
import 'package:mtcs_mobile/widgets/shared_widgets.dart';

class HistoryScreen extends StatefulWidget {
  const HistoryScreen({Key? key}) : super(key: key);

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  String _selectedPeriod = 'today';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Provider.of<TradingProvider>(context, listen: false).fetchHistory(period: _selectedPeriod);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Trade History'),
        actions: [
          PopupMenuButton<String>(
            icon: const Icon(Icons.filter_list),
            onSelected: (value) {
              setState(() => _selectedPeriod = value);
              Provider.of<TradingProvider>(context, listen: false).fetchHistory(period: value);
            },
            itemBuilder: (context) => [
              const PopupMenuItem(value: 'today', child: Text('Today')),
              const PopupMenuItem(value: 'week', child: Text('This Week')),
              const PopupMenuItem(value: 'month', child: Text('This Month')),
              const PopupMenuItem(value: 'all', child: Text('All Time')),
            ],
          ),
        ],
      ),
      body: Consumer<TradingProvider>(
        builder: (context, provider, child) {
          if (provider.isLoadingHistory) {
            return const Center(child: CircularProgressIndicator());
          }

          if (provider.history.isEmpty) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.history, size: 64, color: Theme.of(context).colorScheme.outline),
                  const SizedBox(height: 16),
                  Text("No trading history", style: Theme.of(context).textTheme.titleMedium?.copyWith(color: Theme.of(context).colorScheme.onSurfaceVariant)),
                ],
              ),
            );
          }

          final totalProfit = provider.history.fold<double>(0.0, (sum, item) => sum + item.profit);

          return RefreshIndicator(
            onRefresh: () => provider.fetchHistory(period: _selectedPeriod),
            child: Column(
              children: [
                Container(
                  padding: const EdgeInsets.all(16),
                  color: Theme.of(context).cardColor,
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text("Period P/L:", style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                      Text(
                        "\$${totalProfit.toStringAsFixed(2)}",
                        style: TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                          color: totalProfit >= 0 ? Colors.green : Colors.red,
                        ),
                      )
                    ],
                  ),
                ),
                Expanded(
                  child: ListView.builder(
                    itemCount: provider.history.length,
                    itemBuilder: (context, index) {
                      final h = provider.history[index];
                      final isBuy = h.type == 0;
                      return Card(
                        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
                        child: ListTile(
                          leading: StatusBadge(status: isBuy ? 'BUY' : 'SELL', isGood: isBuy),
                          title: Text("${h.symbol}  ${h.volume} lots", style: const TextStyle(fontWeight: FontWeight.bold)),
                          subtitle: Text("Open: ${h.priceOpen} | Close: ${h.priceCurrent}"),
                          trailing: Text(
                            "\$${h.profit.toStringAsFixed(2)}",
                            style: TextStyle(
                              color: h.profit >= 0 ? Colors.green : Colors.red,
                              fontWeight: FontWeight.bold,
                              fontSize: 16,
                            ),
                          ),
                        ),
                      );
                    },
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
