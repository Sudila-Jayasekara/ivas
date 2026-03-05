export interface Assignment {
    assignment_id: string;
    title: string;
    description: string;
    course_id: string;
    instructor_id: string;
}

export interface Student {
    id: string;
    name: string;
    email?: string;
    course_id?: string;
}

export interface Course {
    id: string;
    name: string;
    programming_language: string;
}

export interface Instructor {
    id: string;
    name: string;
    email: string;
}

export interface GradingCriteria {
    id: string;
    assignment_id: string;
    competency: string;
    difficulty_level: number;
    level_label: string;
    level_description: string;
    marking_criteria: string;
    programming_language: string;
    learning_objectives: string[];
    created_at: string;
    updated_at: string;
}

export interface Question {
    id: string;
    assignment_id: string;
    criteria_id: string;
    text: string;
    expected_answer: string;
    difficulty: number;
    status: string;
}

export interface AssessmentSession {
    id: string;
    student_id: string;
    assignment_id: string;
    status: 'active' | 'completed' | 'abandoned';
    current_question_id?: string;
    started_at: string;
    ended_at?: string;
}

export interface ProviderInfo {
    active_provider: string;
    provider_display: string;
    supported_providers: string[];
}
