import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:mtcs_mobile/providers/quotes_provider.dart';
import 'package:mtcs_mobile/providers/trading_provider.dart';
import 'package:mtcs_mobile/widgets/trade_widget.dart';

class QuotesScreen extends StatefulWidget {
  const QuotesScreen({Key? key}) : super(key: key);

  @override
  State<QuotesScreen> createState() => _QuotesScreenState();
}

class _QuotesScreenState extends State<QuotesScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Provider.of<QuotesProvider>(context, listen: false).startPolling();
    });
  }

  @override
  void dispose() {
    Provider.of<QuotesProvider>(context, listen: false).stopPolling();
    super.dispose();
  }

  void _showTradeDialog(BuildContext context, String symbol, bool isBuy) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Theme.of(context).scaffoldBackgroundColor,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (context) => TradeWidget(symbol: symbol, isBuy: isBuy),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Live Quotes'),
      ),
      body: Consumer<QuotesProvider>(
        builder: (context, provider, child) {
          if (provider.quotes.isEmpty) {
            return const Center(child: CircularProgressIndicator());
          }
          return RefreshIndicator(
            onRefresh: () async => provider.fetchQuotes(),
            child: ListView.builder(
              itemCount: provider.quotes.length,
              itemBuilder: (context, index) {
                final q = provider.quotes[index];
                return Card(
                  margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                  child: ListTile(
                    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    title: Text(q.symbol, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
                    subtitle: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Expanded(
                          child: InkWell(
                            onTap: () => _showTradeDialog(context, q.symbol, false),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                const Text("Bid (Sell)", style: TextStyle(color: Colors.red, fontSize: 12)),
                                Text(q.bid.toString(), style: const TextStyle(fontSize: 18)),
                              ],
                            ),
                          ),
                        ),
                        Expanded(
                          child: InkWell(
                            onTap: () => _showTradeDialog(context, q.symbol, true),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.end,
                              children: [
                                const Text("Ask (Buy)", style: TextStyle(color: Colors.green, fontSize: 12)),
                                Text(q.ask.toString(), style: const TextStyle(fontSize: 18)),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }
}
