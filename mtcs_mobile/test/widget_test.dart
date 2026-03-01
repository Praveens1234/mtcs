import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';
import 'package:mtcs_mobile/main.dart';
import 'package:mtcs_mobile/providers/theme_provider.dart';
import 'package:mtcs_mobile/providers/settings_provider.dart';
import 'package:mtcs_mobile/providers/engine_provider.dart';
import 'package:mtcs_mobile/providers/accounts_provider.dart';
import 'package:mtcs_mobile/providers/quotes_provider.dart';
import 'package:mtcs_mobile/providers/trading_provider.dart';

void main() {
  testWidgets('App loads smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(
      MultiProvider(
        providers: [
          ChangeNotifierProvider(create: (_) => ThemeProvider()),
          ChangeNotifierProvider(create: (_) => SettingsProvider()),
          ChangeNotifierProvider(create: (_) => EngineProvider()),
          ChangeNotifierProvider(create: (_) => AccountsProvider()),
          ChangeNotifierProvider(create: (_) => QuotesProvider()),
          ChangeNotifierProvider(create: (_) => TradingProvider()),
        ],
        child: const MtcsMobileApp(),
      ),
    );

    expect(find.text('MTCS Dashboard'), findsWidgets);
  });
}
