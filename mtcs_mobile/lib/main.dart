import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:mtcs_mobile/providers/theme_provider.dart';
import 'package:mtcs_mobile/providers/settings_provider.dart';
import 'package:mtcs_mobile/providers/engine_provider.dart';
import 'package:mtcs_mobile/providers/accounts_provider.dart';
import 'package:mtcs_mobile/providers/quotes_provider.dart';
import 'package:mtcs_mobile/providers/trading_provider.dart';
import 'package:mtcs_mobile/utils/theme.dart';
import 'package:mtcs_mobile/utils/router.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(
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
}

class MtcsMobileApp extends StatelessWidget {
  const MtcsMobileApp({Key? key}) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return Consumer<ThemeProvider>(
      builder: (context, themeProvider, child) {
        return MaterialApp.router(
          title: 'MTCS Mobile',
          theme: AppTheme.lightTheme,
          darkTheme: AppTheme.darkTheme,
          themeMode: themeProvider.themeMode,
          routerConfig: appRouter,
          debugShowCheckedModeBanner: false,
        );
      },
    );
  }
}
