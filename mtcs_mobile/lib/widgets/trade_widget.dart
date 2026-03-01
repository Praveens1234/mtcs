import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:mtcs_mobile/providers/trading_provider.dart';

class TradeWidget extends StatefulWidget {
  final String symbol;
  final bool isBuy;

  const TradeWidget({Key? key, required this.symbol, required this.isBuy}) : super(key: key);

  @override
  State<TradeWidget> createState() => _TradeWidgetState();
}

class _TradeWidgetState extends State<TradeWidget> {
  final _lotController = TextEditingController(text: '0.01');
  final _slController = TextEditingController();
  final _tpController = TextEditingController();

  @override
  void dispose() {
    _lotController.dispose();
    _slController.dispose();
    _tpController.dispose();
    super.dispose();
  }

  void _executeTrade() async {
    final trading = Provider.of<TradingProvider>(context, listen: false);
    final payload = {
      'symbol': widget.symbol,
      'action': widget.isBuy ? 'buy' : 'sell',
      'volume': double.tryParse(_lotController.text) ?? 0.01,
      'sl': double.tryParse(_slController.text),
      'tp': double.tryParse(_tpController.text),
    };

    try {
      await trading.executeTrade(payload);
      if (mounted) {
        Navigator.pop(context);
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Trade Executed Successfully')));
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Execution failed: $e'), backgroundColor: Colors.red));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom, left: 24, right: 24, top: 24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text("New Order: ${widget.symbol}", style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold)),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                decoration: BoxDecoration(color: widget.isBuy ? Colors.green.withOpacity(0.1) : Colors.red.withOpacity(0.1), borderRadius: BorderRadius.circular(20)),
                child: Text(widget.isBuy ? 'BUY' : 'SELL', style: TextStyle(color: widget.isBuy ? Colors.green : Colors.red, fontWeight: FontWeight.bold)),
              ),
            ],
          ),
          const SizedBox(height: 24),
          TextField(
            controller: _lotController,
            keyboardType: const TextInputType.numberWithOptions(decimal: true),
            decoration: const InputDecoration(labelText: 'Volume (Lots)', border: OutlineInputBorder(), prefixIcon: Icon(Icons.analytics_outlined)),
          ),
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _slController,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(labelText: 'Stop Loss', border: OutlineInputBorder(), hintText: '0.00000'),
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: TextField(
                  controller: _tpController,
                  keyboardType: const TextInputType.numberWithOptions(decimal: true),
                  decoration: const InputDecoration(labelText: 'Take Profit', border: OutlineInputBorder(), hintText: '0.00000'),
                ),
              ),
            ],
          ),
          const SizedBox(height: 32),
          FilledButton(
            onPressed: _executeTrade,
            style: FilledButton.styleFrom(
              backgroundColor: widget.isBuy ? Colors.green : Colors.red,
              minimumSize: const Size.fromHeight(56),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
            child: Text('EXECUTE ${widget.isBuy ? 'BUY' : 'SELL'} AT MARKET', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.white)),
          ),
          const SizedBox(height: 32),
        ],
      ),
    );
  }
}
