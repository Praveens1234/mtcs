class AccountModel {
  final int id;
  final String role;
  final int login;
  final String server;
  final String alias;
  final String nodeState;

  AccountModel({
    required this.id,
    required this.role,
    required this.login,
    required this.server,
    required this.alias,
    required this.nodeState,
  });

  factory AccountModel.fromJson(Map<String, dynamic> json) {
    return AccountModel(
      id: json['id'] ?? 0,
      role: json['role'] ?? '',
      login: json['login'] ?? 0,
      server: json['server'] ?? '',
      alias: json['alias'] ?? '',
      nodeState: json['node_state'] ?? 'UNKNOWN',
    );
  }
}
