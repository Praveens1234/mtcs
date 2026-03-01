class PositionModel {
  final int ticket;
  final String symbol;
  final int type;
  final double volume;
  final double priceOpen;
  final double currentPrice;
  final double sl;
  final double tp;
  final double profit;
  final int time;

  PositionModel({
    required this.ticket,
    required this.symbol,
    required this.type,
    required this.volume,
    required this.priceOpen,
    required this.currentPrice,
    required this.sl,
    required this.tp,
    required this.profit,
    required this.time,
  });

  factory PositionModel.fromJson(Map<String, dynamic> json) {
    return PositionModel(
      ticket: json['ticket'] ?? 0,
      symbol: json['symbol'] ?? '',
      type: json['type'] ?? 0,
      volume: (json['volume'] ?? 0.0).toDouble(),
      priceOpen: (json['price_open'] ?? 0.0).toDouble(),
      currentPrice: (json['current_price'] ?? 0.0).toDouble(),
      sl: (json['sl'] ?? 0.0).toDouble(),
      tp: (json['tp'] ?? 0.0).toDouble(),
      profit: (json['profit'] ?? 0.0).toDouble(),
      time: json['time'] ?? 0,
    );
  }
}
