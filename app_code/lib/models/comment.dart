class CommentRow {
  final int id;
  final int? eventId;
  final String author;
  final String message;
  final DateTime createdAt;

  CommentRow({
    required this.id,
    this.eventId,
    required this.author,
    required this.message,
    required this.createdAt,
  });

  factory CommentRow.fromJson(Map<String, dynamic> j) => CommentRow(
    id: (j['id'] as num).toInt(),
    eventId: (j['event_id'] as num?)?.toInt(),
    author: (j['author'] ?? '').toString(),
    message: (j['message'] ?? '').toString(),
    createdAt: DateTime.tryParse(j['created_at'] ?? '') ?? DateTime.now(),
  );
}
