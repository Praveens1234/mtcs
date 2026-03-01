class HistoryModel {
  final int ticket;
  final String symbol;
  final int type;
  final double volume;
  final double priceOpen;
  final double priceCurrent;
  final double profit;
  final int timeSetup;

  HistoryModel({
    required this.ticket,
    required this.symbol,
    required this.type,
    required this.volume,
    required this.priceOpen,
    required this.priceCurrent,
    required this.profit,
    required this.timeSetup,
  });

  factory HistoryModel.fromJson(Map<String, dynamic> json) {
    return HistoryModel(
      ticket: json['ticket'] ?? 0,
      symbol: json['symbol'] ?? '',
      type: json['type'] ?? 0,
      volume: (json['volume'] ?? 0.0).toDouble(),
      priceOpen: (json['price_open'] ?? 0.0).toDouble(),
      priceCurrent: (json['price_current'] ?? 0.0).toDouble(),
      profit: (json['profit'] ?? 0.0).toDouble(),
      timeSetup: json['time_setup'] ?? 0,
    );
  }
}
