class QuoteModel {
  final String symbol;
  final double bid;
  final double ask;

  QuoteModel({
    required this.symbol,
    required this.bid,
    required this.ask,
  });

  factory QuoteModel.fromJson(Map<String, dynamic> json) {
    return QuoteModel(
      symbol: json['symbol'] ?? '',
      bid: (json['bid'] ?? 0.0).toDouble(),
      ask: (json['ask'] ?? 0.0).toDouble(),
    );
  }
}
